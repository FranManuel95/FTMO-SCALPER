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

from .live_data_loader import LiveDataLoader
from .mt5_client import MT5Client
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
    _positions: dict[int, LivePosition] = field(default_factory=dict)
    _state: StrategyState = field(default_factory=StrategyState)
    _data_loader: LiveDataLoader = field(init=False)
    _order_manager: OrderManager = field(init=False)
    _trail_managers: dict[str, TrailManager] = field(default_factory=dict)
    _daily_guard: DailyLossGuard = field(init=False)
    _max_guard: MaxLossGuard = field(init=False)

    def __post_init__(self) -> None:
        self._data_loader = LiveDataLoader(self.client)
        self._order_manager = OrderManager(self.client, dry_run=self.dry_run, magic=self.magic)
        for s in self.strategies:
            self._trail_managers[s.strategy_id] = TrailManager(
                self._order_manager, trail_atr_mult=s.trail_atr_mult
            )

        initial_balance = self.client.account_balance()
        self._daily_guard = DailyLossGuard(initial_balance, max_daily_loss_pct=0.05)
        self._max_guard = MaxLossGuard(initial_balance, max_loss_pct=0.10)
        logger.info(
            f"PortfolioRunner inicializado | balance={initial_balance:.2f} | "
            f"strategies={[s.strategy_id for s in self.strategies]} | dry_run={self.dry_run}"
        )

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
            return

        self._state.prune(now)
        self._sync_positions()

        latest_bars_by_symbol: dict[str, pd.DataFrame] = {}

        for cfg in self.strategies:
            try:
                df = self._data_loader.get_closed_bars(cfg.symbol, cfg.timeframe, cfg.bars_to_fetch)
            except Exception as e:
                logger.error(f"[{cfg.strategy_id}] fetch bars falló: {e}")
                continue
            latest_bars_by_symbol[cfg.symbol] = df

            try:
                signals = cfg.generator(df)
            except Exception as e:
                logger.exception(f"[{cfg.strategy_id}] generator lanzó: {e}")
                continue
            new_signals = self._filter_new_signals(cfg.strategy_id, signals)
            if not new_signals:
                continue

            for sig in new_signals:
                try:
                    self._process_signal(cfg, sig, df, now)
                except Exception as e:
                    logger.exception(f"[{cfg.strategy_id}] process_signal lanzó: {e}")

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
    ) -> None:
        self._state.mark_seen(cfg.strategy_id, sig.symbol, sig.timestamp)

        # Solo ejecutar si la señal es "reciente" (última barra cerrada)
        last_bar_ts = df.index[-1].to_pydatetime()
        if sig.timestamp < last_bar_ts:
            logger.debug(
                f"[{cfg.strategy_id}] señal histórica descartada "
                f"sig_ts={sig.timestamp} last_bar={last_bar_ts}"
            )
            return

        if self._daily_guard.is_blocked(now):
            logger.warning(f"[{cfg.strategy_id}] DailyLossGuard bloquea — señal descartada")
            return
        if self._max_guard.is_triggered():
            logger.error(f"[{cfg.strategy_id}] MaxLossGuard activo — parar operativa")
            return

        atr = self._extract_atr(df, cfg.atr_column)
        if atr <= 0:
            logger.warning(f"[{cfg.strategy_id}] ATR inválido ({atr}) — señal descartada")
            return

        balance = self.client.account_balance()
        ticket = self._order_manager.place_market_order(
            signal=sig,
            account_balance=balance,
            risk_pct=cfg.risk_pct,
            strategy_id=cfg.strategy_id,
            atr_at_signal=atr,
        )
        if ticket is None:
            return

        volume = float(
            balance * cfg.risk_pct / abs(sig.entry_price - sig.stop_loss)
        )
        self._positions[ticket] = LivePosition(
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
            # buscar el deal de cierre
            deals = mt5.history_deals_get(position=ticket)
            if not deals:
                continue
            pnl = sum(d.profit for d in deals)
            close_time = datetime.fromtimestamp(deals[-1].time, tz=timezone.utc)
            logger.info(f"CLOSED ticket={ticket} pnl={pnl:.2f} strategy={pos.strategy_id}")
            self._daily_guard.record_pnl(pnl, close_time)
            self._max_guard.update(pnl)

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
