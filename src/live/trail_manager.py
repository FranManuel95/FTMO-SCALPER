"""
TrailManager — actualiza el SL de posiciones abiertas según la misma lógica
de trailing stop que usa run_backtest.py.

Cada barra cerrada:
  new_trail_sl_long  = max_high_since_entry - atr_at_signal × trail_mult
  new_trail_sl_short = min_low_since_entry  + atr_at_signal × trail_mult

Si el nuevo SL es más agresivo que el actual, se envía un modify a MT5.
El ATR se fija en el momento de la señal (como en el backtest) — no
recalcula con cada barra para mantener consistencia.
"""
from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

from src.core.types import Side

from .order_manager import LivePosition, OrderManager

logger = logging.getLogger(__name__)


class TrailManager:
    def __init__(self, order_manager: OrderManager, trail_atr_mult: float = 0.5):
        self.order_manager = order_manager
        self.trail_atr_mult = trail_atr_mult

    def update_all(
        self,
        positions: Iterable[LivePosition],
        latest_bars: dict[str, pd.DataFrame],
    ) -> int:
        """
        Recorre todas las posiciones y actualiza su SL si procede.

        latest_bars: dict símbolo → DataFrame con al menos la última barra cerrada.
        Devuelve el número de modificaciones enviadas.
        """
        n_updates = 0
        for pos in positions:
            df = latest_bars.get(pos.symbol)
            if df is None or df.empty:
                continue

            # Only use bars that closed AFTER the position was opened.
            # Using the signal bar's intrabar high/low would move the SL to within
            # centimes of the entry price before the position has a chance to develop.
            bars_after = df[df.index > pd.Timestamp(pos.entry_time)]
            if bars_after.empty:
                continue

            pos.highest_since_entry = max(pos.highest_since_entry, float(bars_after["high"].max()))
            pos.lowest_since_entry  = min(pos.lowest_since_entry,  float(bars_after["low"].min()))

            new_sl = self._compute_trail_sl(pos)
            if new_sl is None:
                continue

            if self._is_improvement(pos, new_sl):
                if self.order_manager.modify_stop_loss(pos.ticket, new_sl):
                    logger.info(
                        f"TRAIL {pos.symbol} ticket={pos.ticket} "
                        f"{pos.stop_loss:.5f} → {new_sl:.5f} "
                        f"(high_since_entry={pos.highest_since_entry:.5f})"
                    )
                    pos.stop_loss = new_sl
                    n_updates += 1
        return n_updates

    def _compute_trail_sl(self, pos: LivePosition) -> float | None:
        if pos.atr_at_signal <= 0:
            return None
        offset = pos.atr_at_signal * self.trail_atr_mult
        if pos.side == Side.LONG:
            return pos.highest_since_entry - offset
        return pos.lowest_since_entry + offset

    def _is_improvement(self, pos: LivePosition, new_sl: float) -> bool:
        """Solo mover SL si es más favorable — nunca relajarlo."""
        if pos.side == Side.LONG:
            return new_sl > pos.stop_loss
        return new_sl < pos.stop_loss
