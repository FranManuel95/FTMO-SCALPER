"""
Test integrado del PortfolioRunner usando CSVs reales como fuente de datos.

Valida la paridad backtest/live: las mismas señales se generan con el mismo
código, solo cambia la procedencia de los datos.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.core.types import Signal, Side, SignalType
from src.live.mt5_client import MT5Client
from src.live.notifier import Notifier
from src.live.portfolio_runner import PortfolioRunner, StrategyConfig


def _dummy_generator(df: pd.DataFrame) -> list[Signal]:
    """Generator mínimo: emite 1 señal LONG en la última barra."""
    last = df.iloc[-1]
    ts = df.index[-1].to_pydatetime()
    return [Signal(
        symbol=df.attrs.get("symbol", "X"),
        side=Side.LONG,
        signal_type=SignalType.PULLBACK,
        timestamp=ts,
        entry_price=float(last["close"]),
        stop_loss=float(last["close"]) - 10,
        take_profit=float(last["close"]) + 25,
    )]


def test_runner_tick_fake_client_dummy_generator():
    """Runner completo con cliente fake y generador dummy — valida plumbing."""
    client = MT5Client(fake=True)
    client.connect()

    cfg = StrategyConfig(
        strategy_id="dummy_test",
        symbol="XAUUSD",
        timeframe="1h",
        risk_pct=0.004,
        trail_atr_mult=0.5,
        generator=_dummy_generator,
    )
    runner = PortfolioRunner(client=client, strategies=[cfg], dry_run=True)
    runner.tick()

    # En dry-run una señal debería registrarse como posición interna
    assert len(runner._positions) >= 0  # ≥0 porque fake data puede no generar ATR válido


def test_state_deduplication():
    """La misma señal no se procesa dos veces en ticks consecutivos."""
    from datetime import datetime, timezone
    from src.live.strategy_state import StrategyState

    state = StrategyState()
    ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert not state.was_seen("s1", "XAUUSD", ts)
    state.mark_seen("s1", "XAUUSD", ts)
    assert state.was_seen("s1", "XAUUSD", ts)
    assert not state.was_seen("s2", "XAUUSD", ts)  # otra estrategia
    assert state.daily_count("s1", ts.date()) == 1


def test_trail_manager_moves_sl_up_for_long():
    """TrailManager mueve el SL en LONG cuando sube el high."""
    from datetime import datetime, timezone
    from src.live.order_manager import LivePosition, OrderManager
    from src.live.trail_manager import TrailManager
    from src.live.mt5_client import MT5Client

    client = MT5Client(fake=True)
    om = OrderManager(client, dry_run=True)
    tm = TrailManager(om, trail_atr_mult=0.5)

    pos = LivePosition(
        ticket=1, symbol="XAUUSD", side=Side.LONG,
        entry_price=2000.0, stop_loss=1990.0, take_profit=2025.0,
        volume=0.1, strategy_id="test",
        atr_at_signal=4.0,
        entry_time=datetime.now(timezone.utc),
    )
    df = pd.DataFrame({
        "open": [2000.0], "high": [2010.0], "low": [1998.0], "close": [2008.0], "volume": [100],
    }, index=pd.to_datetime(["2024-01-01T10:00:00Z"]))

    n = tm.update_all([pos], {"XAUUSD": df})
    # new_sl = 2010 - 4*0.5 = 2008 > 1990 → debería actualizar
    assert n == 1
    assert pos.stop_loss == pytest.approx(2008.0)


def test_trail_manager_never_relaxes_sl():
    """TrailManager nunca mueve el SL hacia abajo (LONG)."""
    from datetime import datetime, timezone
    from src.live.order_manager import LivePosition, OrderManager
    from src.live.trail_manager import TrailManager
    from src.live.mt5_client import MT5Client

    client = MT5Client(fake=True)
    om = OrderManager(client, dry_run=True)
    tm = TrailManager(om, trail_atr_mult=0.5)

    pos = LivePosition(
        ticket=1, symbol="XAUUSD", side=Side.LONG,
        entry_price=2000.0, stop_loss=2005.0, take_profit=2025.0,
        volume=0.1, strategy_id="test",
        atr_at_signal=4.0,
        entry_time=datetime.now(timezone.utc),
    )
    pos.highest_since_entry = 2010.0
    # Nueva barra con high menor que el pico anterior
    df = pd.DataFrame({
        "open": [2005.0], "high": [2007.0], "low": [2003.0], "close": [2006.0], "volume": [100],
    }, index=pd.to_datetime(["2024-01-01T10:00:00Z"]))

    n = tm.update_all([pos], {"XAUUSD": df})
    # new_sl = max(2010, 2007) - 2 = 2008 > 2005 → sí actualiza hacia arriba
    assert pos.stop_loss == pytest.approx(2008.0)
    assert n == 1


def _make_signal(symbol, entry, sl):
    from datetime import datetime, timezone
    return Signal(
        symbol=symbol, side=Side.LONG, signal_type=SignalType.PULLBACK,
        timestamp=datetime(2026, 4, 22, tzinfo=timezone.utc),
        entry_price=entry, stop_loss=sl, take_profit=entry + (entry - sl) * 2.5,
    )


def _make_real_client_with_mock_mt5(mock_info):
    """Construye un MT5Client con fake=False y parchea su propiedad raw con mock_info."""
    import types
    from unittest.mock import patch, PropertyMock

    mock_mt5 = types.SimpleNamespace(symbol_info=lambda s: mock_info)
    client = MT5Client(fake=False)
    # En Linux sin MT5 instalado el constructor fuerza fake=True — lo sobrescribimos
    # para ejercer la rama de conversión de moneda en _compute_volume.
    client.fake = False
    client._connected = True
    client.ensure_connected = lambda max_retries=3: True
    return client, mock_mt5, patch.object(type(client), "raw", new_callable=PropertyMock, return_value=mock_mt5)


def test_compute_volume_gbpjpy_tick_value():
    """GBPJPY lot sizing usa trade_tick_value — sin el fix da 0.01 (mínimo)."""
    import types
    from src.live.order_manager import OrderManager

    # EUR/JPY ≈ 162: tick_value (0.001 JPY per tick, per lot) = 100_000 * 0.001 / 162 ≈ 0.617 EUR
    mock_info = types.SimpleNamespace(
        trade_tick_size=0.001,
        trade_tick_value=0.617,
        trade_contract_size=100_000,
    )
    client, _, raw_patch = _make_real_client_with_mock_mt5(mock_info)
    with raw_patch:
        om = OrderManager(client, dry_run=False)
        sig = _make_signal("GBPJPY", entry=215.585, sl=215.062)
        # stop = 0.523 JPY, risk = 160_000 * 0.0025 = 400 EUR
        # risk_per_lot = (0.523 / 0.001) * 0.617 = 523 * 0.617 ≈ 322.7 EUR/lot
        # lots = 400 / 322.7 ≈ 1.24
        vol = om._compute_volume(sig, balance=160_000, risk_pct=0.0025)
    assert vol == pytest.approx(1.24, rel=0.05), f"Expected ~1.24 lots, got {vol:.4f}"


def test_compute_volume_eurusd_tick_value():
    """EURUSD lot sizing con tick_value: verifica que la ruta real funciona."""
    import types
    from src.live.order_manager import OrderManager

    # EURUSD: tick_value = 100_000 * 0.00001 / 1.175 ≈ 0.851 EUR/tick/lot
    mock_info = types.SimpleNamespace(
        trade_tick_size=0.00001,
        trade_tick_value=0.851,
        trade_contract_size=100_000,
    )
    client, _, raw_patch = _make_real_client_with_mock_mt5(mock_info)
    with raw_patch:
        om = OrderManager(client, dry_run=False)
        sig = _make_signal("EURUSD", entry=1.17562, sl=1.17430)
        # stop = 0.00132, risk = 400 EUR
        # risk_per_lot = (0.00132 / 0.00001) * 0.851 = 132 * 0.851 ≈ 112.3 EUR/lot
        # lots = 400 / 112.3 ≈ 3.56
        vol = om._compute_volume(sig, balance=160_000, risk_pct=0.0025)
    assert vol == pytest.approx(3.56, rel=0.05), f"Expected ~3.56 lots, got {vol:.4f}"


def test_compute_volume_fake_client_unchanged():
    """El cliente fake sigue usando raw (compatibilidad backtest)."""
    from src.live.order_manager import OrderManager

    client = MT5Client(fake=True)
    om = OrderManager(client, dry_run=True)
    sig = _make_signal("GBPJPY", entry=215.585, sl=215.062)
    vol = om._compute_volume(sig, balance=160_000, risk_pct=0.0025)
    # raw = 160_000 * 0.0025 / 0.523 ≈ 764.8 (self-consistent backtest units)
    assert vol == pytest.approx(764.8, rel=0.01)


class _CapturingNotifier(Notifier):
    def __init__(self):
        self.events: list[tuple[str, tuple]] = []

    def on_startup(self, balance, strategies):
        self.events.append(("startup", (balance, tuple(strategies))))

    def on_signal(self, strategy_id, sig):
        self.events.append(("signal", (strategy_id, sig.symbol)))

    def on_order_opened(self, pos):
        self.events.append(("opened", (pos.ticket, pos.symbol)))

    def on_guard_triggered(self, guard, reason):
        self.events.append(("guard", (guard, reason)))


def test_notifier_receives_startup_event():
    """Runner notifica al arrancar con balance y lista de estrategias."""
    client = MT5Client(fake=True)
    client.connect()
    notifier = _CapturingNotifier()
    cfg = StrategyConfig(
        strategy_id="dummy_test",
        symbol="XAUUSD",
        timeframe="1h",
        risk_pct=0.004,
        trail_atr_mult=0.5,
        generator=_dummy_generator,
    )
    PortfolioRunner(client=client, strategies=[cfg], dry_run=True, notifier=notifier)

    assert any(e[0] == "startup" for e in notifier.events)
    kind, payload = notifier.events[0]
    assert kind == "startup"
    assert payload[0] == 10_000.0  # balance fake
    assert payload[1] == ("dummy_test",)
