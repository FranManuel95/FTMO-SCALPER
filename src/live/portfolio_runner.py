"""
PortfolioRunner — loop principal que ejecuta las N estrategias validadas en live.

Cada iteración (al cierre de cada barra):
  1. Verificar conexión MT5
  2. Para cada estrategia:
       a. Descargar barras cerradas
       b. Ejecutar signal generator
       c. Filtrar señales nuevas (no vistas antes)
       d. Verificar DailyLossGuard
       e. Placear orden si procede
  3. Actualizar trailing stops de posiciones abiertas
  4. Sincronizar estado con MT5 (posiciones cerradas)
  5. Dormir hasta el próximo cierre de barra

El runner NO reescribe lógica de señales — reutiliza los generators existentes
pasándoles un DataFrame descargado live. Esto garantiza paridad 1:1 con backtest.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from src.core.types import Side, Signal
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.max_loss_guard import MaxLossGuard

from .event_logger import EventLogger, NullEventLogger
from .live_data_loader import LiveDataLoader
from .mt5_client import MT5Client
from .notifier import NullNotifier, Notifier
from .order_manager import LivePosition, OrderManager
from .strategy_state import StrategyState
from .trail_manager import TrailManager

logger = logging.getLogger(__name__)


SignalGeneratorFn = Callable[[pd.DataFrame], list[Signal]]


@dataclass
class StrategyConfig:
    strategy_id: str          # "xauusd_pullback_1h", etc.
    symbol: str
    timeframe: str            # "1h", "15m", "4h"
    risk_pct: float           # 0.004, 0.0025, etc.
    trail_atr_mult: float     # 0.5, 0.2, 0.3
    generator: SignalGeneratorFn
    bars_to_fetch: int = 500  # ventana de datos para el generator
    atr_column: str = "atr_14"


@dataclass
class PortfolioRunner:
    client: MT5Client
    strategies: list[StrategyConfig]
    dry_run: bool = True
    tick_interval_seconds: int = 30
    magic: int = 90210
    notifier: Notifier = field(default_factory=NullNotifier)
    event_logger: EventLogger | NullEventLogger = field(default_factory=NullEventLogger)
    _positions: dict[int, LivePosition] = field(default_factory=dict)
    _state: StrategyState = field(default_factory=StrategyState)
    _data_loader: LiveDataLoader = field(init=False)
    _order_manager: OrderManager = field(init=False)
    _trail_managers: dict[str, TrailManager] = field(default_factory=dict)
    _daily_guard: DailyLossGuard = field(init=False)
    _max_guard: MaxLossGuard = field(init=False)
    _last_snapshot_unix: float = 0.0

    def __post_init__(self) -> None:
        self._data_loader = LiveDataLoader(self.client)
        self._order_manager = OrderManager(
            self.client, dry_run=self.dry_run, magic=self.magic,
            event_logger=self.event_logger,
        )
        for s in self.strategies:
            self._trail_managers[s.strategy_id] = TrailManager(
                self._order_manager, trail_atr_mult=s.trail_atr_mult,
                event_logger=self.event_logger,
            )

        initial_balance = self.client.account_balance()
        self._daily_guard = DailyLossGuard(initial_balance, max_daily_loss_pct=0.05)
        self._max_guard = MaxLossGuard(initial_balance, max_loss_pct=0.10)
        logger.info(
            f"PortfolioRunner inicializado | balance={initial_balance:.2f} | "
            f"strategies={[s.strategy_id for s in self.strategies]} | dry_run={self.dry_run}"
        )
        self.notifier.on_startup(initial_balance, [s.strategy_id for s in self.strategies])
        self.event_logger.system_event(
            "bot_start",
            initial_balance=initial_balance,
            strategies=[s.strategy_id for s in self.strategies],
            dry_run=self.dry_run,
        )
        self._recover_open_positions()

    # ── Loop principal ────────────────────────────────────────────────────────

    def run_forever(self) -> None:
        logger.info("Entrando en run_forever — Ctrl+C para parar")
        try:
            while True:
                self.tick()
                time.sleep(self.tick_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Interrupción manual — cerrando runner")
        finally:
            self.client.disconnect()

    def tick(self) -> None:
        """Una iteración completa: puede llamarse manualmente desde tests."""
        now = datetime.now(timezone.utc)
        if not self.client.ensure_connected():
            logger.error("MT5 no conectado — skip tick")
            self.event_logger.system_event("mt5_disconnected", ts=now.isoformat())
            return

        self._state.prune(now)
        self._sync_positions()
        self._maybe_emit_market_snapshot(now)

        latest_bars_by_symbol: dict[str, pd.DataFrame] = {}

        for cfg in self.strategies:
            t0 = time.perf_counter()
            error = None
            n_bars = 0
            last_bar_ts = None
            n_signals = 0
            n_filtered = 0
            n_executed = 0

            try:
                df = self._data_loader.get_closed_bars(cfg.symbol, cfg.timeframe, cfg.bars_to_fetch)
                fetch_ms = (time.perf_counter() - t0) * 1000
                n_bars = len(df)
                last_bar_ts = df.index[-1].isoformat() if n_bars else None
                latest_bars_by_symbol[cfg.symbol] = df
            except Exception as e:
                error = f"fetch_failed:{e}"
                logger.error(f"[{cfg.strategy_id}] fetch bars falló: {e}")
                self.event_logger.strategy_tick(
                    strategy_id=cfg.strategy_id, symbol=cfg.symbol,
                    n_bars=0, last_bar_ts=None, n_signals=0, n_filtered=0, n_executed=0,
                    fetch_ms=(time.perf_counter() - t0) * 1000, generator_ms=0.0, error=error,
                )
                continue

            t1 = time.perf_counter()
            try:
                signals = cfg.generator(df)
                generator_ms = (time.perf_counter() - t1) * 1000
                n_signals = len(signals)
            except Exception as e:
                error = f"generator_raised:{e}"
                logger.exception(f"[{cfg.strategy_id}] generator lanzó: {e}")
                self.event_logger.strategy_tick(
                    strategy_id=cfg.strategy_id, symbol=cfg.symbol,
                    n_bars=n_bars, last_bar_ts=last_bar_ts, n_signals=0,
                    n_filtered=0, n_executed=0,
                    fetch_ms=fetch_ms, generator_ms=(time.perf_counter() - t1) * 1000,
                    error=error,
                )
                continue

            new_signals = self._filter_new_signals(cfg.strategy_id, signals)
            n_filtered = n_signals - len(new_signals)

            for sig in new_signals:
                try:
                    if self._process_signal(cfg, sig, df, now):
                        n_executed += 1
                except Exception as e:
                    logger.exception(f"[{cfg.strategy_id}] process_signal lanzó: {e}")

            self.event_logger.strategy_tick(
                strategy_id=cfg.strategy_id, symbol=cfg.symbol,
                n_bars=n_bars, last_bar_ts=last_bar_ts,
                n_signals=n_signals, n_filtered=n_filtered, n_executed=n_executed,
                fetch_ms=fetch_ms, generator_ms=generator_ms, error=error,
            )

        # Actualizar trailing stops — agrupados por estrategia
        for cfg in self.strategies:
            positions = [p for p in self._positions.values() if p.strategy_id == cfg.strategy_id]
            if not positions:
                continue
            df = latest_bars_by_symbol.get(cfg.symbol)
            if df is None:
                continue
            self._trail_managers[cfg.strategy_id].update_all(
                positions=positions,
                latest_bars={cfg.symbol: df},
            )

    def _maybe_emit_market_snapshot(self, now: datetime) -> None:
        """Emite un snapshot de cuenta como mucho una vez por minuto."""
        ts_unix = now.timestamp()
        if ts_unix - self._last_snapshot_unix < 60:
            return
        try:
            balance = self.client.account_balance()
            equity = self.client.account_equity()
            n_open = len(self._positions)
            self.event_logger.market_snapshot(
                equity=equity, balance=balance,
                free_margin=equity, margin=0.0,  # MT5 specifics expanded later if needed
                n_open_positions=n_open,
                daily_pnl=self._daily_guard.daily_pnl(now) if hasattr(self._daily_guard, "daily_pnl") else 0.0,
            )
            self._last_snapshot_unix = ts_unix
        except Exception as e:  # noqa: BLE001
            logger.debug(f"market_snapshot fallo (no crítico): {e}")

    # ── Señales ───────────────────────────────────────────────────────────────

    def _filter_new_signals(self, strategy_id: str, signals: list[Signal]) -> list[Signal]:
        fresh = []
        for sig in signals:
            if self._state.was_seen(strategy_id, sig.symbol, sig.timestamp):
                continue
            fresh.append(sig)
        return fresh

    def _process_signal(
        self,
        cfg: StrategyConfig,
        sig: Signal,
        df: pd.DataFrame,
        now: datetime,
    ) -> bool:
        """Procesa una señal nueva. Devuelve True si se ejecutó como orden."""
        self._state.mark_seen(cfg.strategy_id, sig.symbol, sig.timestamp)

        def _log_signal(was_executed: bool, filter_reason: str | None) -> None:
            self.event_logger.signal(
                strategy_id=cfg.strategy_id, symbol=sig.symbol, side=sig.side.value,
                signal_ts=sig.timestamp.isoformat(),
                entry_price=sig.entry_price, stop_loss=sig.stop_loss,
                take_profit=sig.take_profit, atr_at_signal=0.0,  # actualizado abajo si aplica
                was_executed=was_executed, filter_reason=filter_reason,
            )

        # Solo ejecutar si la señal es "reciente" (última barra cerrada)
        last_bar_ts = df.index[-1].to_pydatetime()
        if sig.timestamp < last_bar_ts:
            logger.debug(
                f"[{cfg.strategy_id}] señal histórica descartada "
                f"sig_ts={sig.timestamp} last_bar={last_bar_ts}"
            )
            _log_signal(False, "stale_signal")
            return False

        if self._daily_guard.is_blocked(now):
            logger.warning(f"[{cfg.strategy_id}] DailyLossGuard bloquea — señal descartada")
            self.notifier.on_guard_triggered(
                "DailyLossGuard", f"[{cfg.strategy_id}] señal descartada"
            )
            self.event_logger.guard_check(
                guard_name="DailyLossGuard", strategy_id=cfg.strategy_id,
                triggered=True, reason="daily_loss_limit_reached",
            )
            _log_signal(False, "daily_guard")
            return False
        if self._max_guard.is_triggered():
            logger.error(f"[{cfg.strategy_id}] MaxLossGuard activo — parar operativa")
            self.notifier.on_guard_triggered(
                "MaxLossGuard", f"[{cfg.strategy_id}] parar operativa"
            )
            self.event_logger.guard_check(
                guard_name="MaxLossGuard", strategy_id=cfg.strategy_id,
                triggered=True, reason="max_loss_limit_reached",
            )
            _log_signal(False, "max_guard")
            return False

        self.notifier.on_signal(cfg.strategy_id, sig)

        atr = self._extract_atr(df, cfg.atr_column)
        if atr <= 0:
            logger.warning(f"[{cfg.strategy_id}] ATR inválido ({atr}) — señal descartada")
            _log_signal(False, "invalid_atr")
            return False

        balance = self.client.account_balance()
        ticket = self._order_manager.place_market_order(
            signal=sig,
            account_balance=balance,
            risk_pct=cfg.risk_pct,
            strategy_id=cfg.strategy_id,
            atr_at_signal=atr,
        )
        if ticket is None:
            self.event_logger.signal(
                strategy_id=cfg.strategy_id, symbol=sig.symbol, side=sig.side.value,
                signal_ts=sig.timestamp.isoformat(),
                entry_price=sig.entry_price, stop_loss=sig.stop_loss,
                take_profit=sig.take_profit, atr_at_signal=atr,
                was_executed=False, filter_reason="order_failed",
            )
            return False

        volume = float(
            balance * cfg.risk_pct / abs(sig.entry_price - sig.stop_loss)
        )
        pos = LivePosition(
            ticket=ticket,
            symbol=sig.symbol,
            side=sig.side,
            entry_price=sig.entry_price,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            volume=volume,
            strategy_id=cfg.strategy_id,
            atr_at_signal=atr,
            entry_time=now,
        )
        self._positions[ticket] = pos
        self.notifier.on_order_opened(pos)
        self.event_logger.signal(
            strategy_id=cfg.strategy_id, symbol=sig.symbol, side=sig.side.value,
            signal_ts=sig.timestamp.isoformat(),
            entry_price=sig.entry_price, stop_loss=sig.stop_loss,
            take_profit=sig.take_profit, atr_at_signal=atr,
            was_executed=True, filter_reason=None,
        )
        return True

    # ── Sincronización con MT5 ────────────────────────────────────────────────

    def _sync_positions(self) -> None:
        """Detecta posiciones cerradas por SL/TP en MT5 y las registra en el PnL diario."""
        if self.dry_run or self.client.fake:
            return
        open_tickets = {p.ticket for p in self._order_manager.open_positions()}
        closed = [t for t in list(self._positions) if t not in open_tickets]
        if not closed:
            return

        mt5 = self.client.raw
        for ticket in closed:
            pos = self._positions.pop(ticket)
            deals = mt5.history_deals_get(position=ticket)
            if not deals:
                continue
            pnl = sum(d.profit for d in deals)
            commission = sum(getattr(d, "commission", 0.0) for d in deals)
            swap = sum(getattr(d, "swap", 0.0) for d in deals)
            net = pnl + commission + swap
            # El último deal del position es el de cierre
            close_deal = deals[-1]
            exit_price = float(close_deal.price)
            close_time = datetime.fromtimestamp(close_deal.time, tz=timezone.utc)
            duration = int((close_time - pos.entry_time).total_seconds())

            close_reason = self._infer_close_reason(pos, exit_price)
            mfe, mae = self._compute_mfe_mae(pos)

            logger.info(
                f"CLOSED ticket={ticket} pnl={pnl:.2f} net={net:.2f} "
                f"reason={close_reason} duration={duration}s strategy={pos.strategy_id}"
            )
            self._daily_guard.record_pnl(pnl, close_time)
            self._max_guard.update(pnl)
            self.notifier.on_position_closed(pos, pnl)
            self.event_logger.position_close(
                strategy_id=pos.strategy_id, symbol=pos.symbol,
                ticket=ticket, side=pos.side.value,
                open_time=pos.entry_time.isoformat(), close_time=close_time.isoformat(),
                duration_seconds=duration,
                entry_price=pos.entry_price, exit_price=exit_price,
                original_sl=pos.original_stop_loss, final_sl=pos.stop_loss,
                take_profit=pos.take_profit, volume=pos.volume,
                pnl=pnl, commission=commission, swap=swap, net=net,
                close_reason=close_reason, mfe=mfe, mae=mae,
            )

    @staticmethod
    def _infer_close_reason(pos: LivePosition, exit_price: float) -> str:
        sl_distance = abs(pos.entry_price - pos.original_stop_loss)
        if sl_distance == 0:
            return "unknown"
        # Tolerancia: 5% de la distancia al SL original (evita falsos negativos por slippage)
        tol = max(sl_distance * 0.05, sl_distance * 0.01)
        if abs(exit_price - pos.take_profit) <= tol:
            return "take_profit"
        if abs(exit_price - pos.stop_loss) <= tol:
            if abs(pos.stop_loss - pos.original_stop_loss) <= tol:
                return "stop_loss"
            return "trail_stop"
        if abs(exit_price - pos.original_stop_loss) <= tol:
            return "stop_loss"
        return "manual_or_unknown"

    @staticmethod
    def _compute_mfe_mae(pos: LivePosition) -> tuple[float, float]:
        """Max Favorable Excursion (positivo = se movió a favor) y MAE (negativo = en contra)."""
        if pos.side == Side.LONG:
            mfe = pos.highest_since_entry - pos.entry_price
            mae = pos.lowest_since_entry - pos.entry_price
        else:
            mfe = pos.entry_price - pos.lowest_since_entry
            mae = pos.entry_price - pos.highest_since_entry
        return mfe, mae

    # ── Recuperación de estado ────────────────────────────────────────────────

    def _recover_open_positions(self) -> None:
        """Al arrancar recupera posiciones abiertas de instancias previas y retoma el trailing."""
        if self.dry_run or self.client.fake:
            return

        open_mt5 = self._order_manager.open_positions()
        if not open_mt5:
            return

        strategy_map = {s.strategy_id: s for s in self.strategies}
        mt5 = self.client.raw
        recovered = 0

        for mt5_pos in open_mt5:
            ticket = mt5_pos.ticket
            if ticket in self._positions:
                continue

            comment = mt5_pos.comment or ""
            strategy_id = comment.removeprefix("strat:").strip()

            cfg = strategy_map.get(strategy_id)
            if cfg is None:
                # El comment puede estar truncado a 20 chars — buscar por prefijo
                matches = [s for s in self.strategies if s.strategy_id.startswith(strategy_id)]
                cfg = matches[0] if len(matches) == 1 else None
            if cfg is None:
                logger.warning(
                    f"RECOVER skip ticket={ticket} comment={comment!r} "
                    f"— no coincide con ninguna estrategia"
                )
                continue

            df = None
            atr = 0.0
            try:
                df = self._data_loader.get_closed_bars(cfg.symbol, cfg.timeframe, cfg.bars_to_fetch)
                atr = self._extract_atr(df, cfg.atr_column)
            except Exception as e:
                logger.warning(f"RECOVER ticket={ticket}: no se pudo obtener ATR — {e}")

            side = Side.LONG if mt5_pos.type == mt5.POSITION_TYPE_BUY else Side.SHORT
            entry_time = datetime.fromtimestamp(mt5_pos.time, tz=timezone.utc)

            highest = mt5_pos.price_open
            lowest = mt5_pos.price_open
            if df is not None and not df.empty:
                bars_since = df[df.index >= pd.Timestamp(entry_time)]
                if not bars_since.empty:
                    highest = max(mt5_pos.price_open, float(bars_since["high"].max()))
                    lowest = min(mt5_pos.price_open, float(bars_since["low"].min()))

            pos = LivePosition(
                ticket=ticket,
                symbol=mt5_pos.symbol,
                side=side,
                entry_price=mt5_pos.price_open,
                stop_loss=mt5_pos.sl,
                take_profit=mt5_pos.tp,
                volume=mt5_pos.volume,
                strategy_id=cfg.strategy_id,
                atr_at_signal=atr,
                entry_time=entry_time,
            )
            pos.highest_since_entry = highest
            pos.lowest_since_entry = lowest

            self._positions[ticket] = pos
            recovered += 1
            logger.info(
                f"RECOVER ticket={ticket} {side.value} {mt5_pos.symbol} "
                f"entry={mt5_pos.price_open} sl={mt5_pos.sl} tp={mt5_pos.tp} "
                f"atr={atr:.5f} highest_since={highest:.5f}"
            )
            self.event_logger.system_event(
                "position_recovered",
                ticket=ticket, symbol=mt5_pos.symbol, strategy_id=cfg.strategy_id,
                side=side.value, entry_price=mt5_pos.price_open,
                stop_loss=mt5_pos.sl, take_profit=mt5_pos.tp,
                volume=mt5_pos.volume, atr_at_signal=atr,
                highest_since_entry=highest, lowest_since_entry=lowest,
            )

        if recovered:
            logger.info(f"RECOVER: {recovered} posición(es) recuperada(s) para trailing")

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _extract_atr(self, df: pd.DataFrame, col: str) -> float:
        if col not in df.columns:
            from src.features.technical.indicators import add_atr
            df2 = add_atr(df.copy(), 14)
            if col not in df2.columns:
                return 0.0
            series = df2[col].dropna()
        else:
            series = df[col].dropna()
        return float(series.iloc[-1]) if len(series) else 0.0
