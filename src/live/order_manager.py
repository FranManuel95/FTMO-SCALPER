"""
OrderManager — capa de ejecución de órdenes en MT5.

Responsabilidades:
  - Convertir Signal → orden MT5 con lot size calculado
  - Validar parámetros antes de enviar (SL > 0, distancias mínimas del broker)
  - Modificar SL de posiciones abiertas (para el trailing stop)
  - Cerrar posiciones manualmente si hace falta
  - Modo dry-run: loguea las acciones sin enviarlas (crítico para testing)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.types import Side, Signal
from src.risk.position_sizing import size_by_fixed_risk

from .mt5_client import MT5Client

logger = logging.getLogger(__name__)


@dataclass
class LivePosition:
    """Representación interna de una posición abierta (para trail y deduplicación)."""
    ticket: int
    symbol: str
    side: Side
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    strategy_id: str
    atr_at_signal: float
    entry_time: datetime
    highest_since_entry: float = field(init=False)
    lowest_since_entry: float = field(init=False)

    def __post_init__(self) -> None:
        self.highest_since_entry = self.entry_price
        self.lowest_since_entry = self.entry_price


class OrderManager:
    def __init__(
        self,
        client: MT5Client,
        dry_run: bool = True,
        magic: int = 90210,
        deviation_points: int = 20,
    ):
        self.client = client
        self.dry_run = dry_run
        self.magic = magic
        self.deviation_points = deviation_points
        if dry_run:
            logger.info("OrderManager en DRY-RUN — las órdenes se simulan")

    # ── Posiciones ────────────────────────────────────────────────────────────

    def place_market_order(
        self,
        signal: Signal,
        account_balance: float,
        risk_pct: float,
        strategy_id: str,
        atr_at_signal: float,
    ) -> Optional[int]:
        """
        Abre posición de mercado respetando el risk sizing.
        Devuelve ticket si éxito, None si falla.
        """
        volume = self._compute_volume(signal, account_balance, risk_pct)
        if volume <= 0:
            logger.warning(f"Volume 0 para señal {signal.symbol} — descartada")
            return None

        volume = self._round_to_lot_step(signal.symbol, volume)
        if volume <= 0:
            logger.warning(f"Volume ajustado a lote mínimo resultó 0 — descartada")
            return None

        if self.dry_run:
            ticket = self._fake_ticket()
            logger.info(
                f"[DRY-RUN] OPEN {signal.side.value} {signal.symbol} "
                f"vol={volume:.2f} @ {signal.entry_price:.5f} "
                f"SL={signal.stop_loss:.5f} TP={signal.take_profit:.5f} "
                f"strategy={strategy_id} ticket={ticket}"
            )
            return ticket

        return self._send_market_order(signal, volume, strategy_id)

    def modify_stop_loss(self, ticket: int, new_sl: float, new_tp: float | None = None) -> bool:
        """Modifica SL de una posición existente (usado por TrailManager)."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] MODIFY ticket={ticket} new_sl={new_sl:.5f}")
            return True

        self.client.ensure_connected()
        mt5 = self.client.raw
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            logger.warning(f"MODIFY: ticket {ticket} no encontrado")
            return False
        p = pos[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": p.symbol,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp if new_tp is not None else p.tp,
            "magic": self.magic,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"MODIFY fallo ticket={ticket} retcode={result.retcode} {result.comment}")
            return False
        return True

    def close_position(self, ticket: int, reason: str = "manual") -> bool:
        if self.dry_run:
            logger.info(f"[DRY-RUN] CLOSE ticket={ticket} reason={reason}")
            return True

        self.client.ensure_connected()
        mt5 = self.client.raw
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return False
        p = pos[0]
        symbol_info = mt5.symbol_info_tick(p.symbol)
        price = symbol_info.bid if p.type == mt5.POSITION_TYPE_BUY else symbol_info.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": price,
            "deviation": self.deviation_points,
            "magic": self.magic,
            "comment": f"close:{reason}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def open_positions(self, magic_filter: bool = True) -> list:
        if self.dry_run or self.client.fake:
            return []
        self.client.ensure_connected()
        positions = self.client.raw.positions_get() or []
        if magic_filter:
            positions = [p for p in positions if p.magic == self.magic]
        return list(positions)

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _send_market_order(self, signal: Signal, volume: float, strategy_id: str) -> Optional[int]:
        self.client.ensure_connected()
        mt5 = self.client.raw
        tick = mt5.symbol_info_tick(signal.symbol)
        if tick is None:
            logger.error(f"Sin tick para {signal.symbol}")
            return None

        if signal.side == Side.LONG:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": signal.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": signal.stop_loss,
            "tp": signal.take_profit,
            "deviation": self.deviation_points,
            "magic": self.magic,
            "comment": f"strat:{strategy_id[:20]}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                f"OPEN fallo {signal.symbol} retcode={result.retcode} comment={result.comment}"
            )
            return None
        logger.info(
            f"OPEN OK ticket={result.order} {signal.side.value} {signal.symbol} "
            f"vol={volume} @ {price} SL={signal.stop_loss} TP={signal.take_profit}"
        )
        return int(result.order)

    def _compute_volume(self, signal: Signal, balance: float, risk_pct: float) -> float:
        return size_by_fixed_risk(balance, risk_pct, signal.entry_price, signal.stop_loss)

    def _round_to_lot_step(self, symbol: str, volume: float) -> float:
        if self.client.fake or self.dry_run:
            return max(0.01, round(volume, 2))
        info = self.client.raw.symbol_info(symbol)
        if info is None:
            return round(volume, 2)
        step = info.volume_step
        min_vol = info.volume_min
        max_vol = info.volume_max
        vol = max(min_vol, round(volume / step) * step)
        return min(vol, max_vol)

    _fake_counter = 1_000_000
    def _fake_ticket(self) -> int:
        OrderManager._fake_counter += 1
        return OrderManager._fake_counter
