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

from .event_logger import EventLogger, NullEventLogger
from .mt5_client import MT5Client

logger = logging.getLogger(__name__)


@dataclass
class LivePosition:
    """Representación interna de una posición abierta (para trail y deduplicación)."""
    ticket: int
    symbol: str
    side: Side
    entry_price: float
    stop_loss: float                              # SL actual (lo modifica el trail)
    take_profit: float
    volume: float
    strategy_id: str
    atr_at_signal: float
    entry_time: datetime
    original_stop_loss: float = field(init=False)  # SL inicial — preservado para close_reason
    highest_since_entry: float = field(init=False)
    lowest_since_entry: float = field(init=False)

    def __post_init__(self) -> None:
        self.original_stop_loss = self.stop_loss
        self.highest_since_entry = self.entry_price
        self.lowest_since_entry = self.entry_price


class OrderManager:
    def __init__(
        self,
        client: MT5Client,
        dry_run: bool = True,
        magic: int = 90210,
        deviation_points: int = 20,
        event_logger: EventLogger | NullEventLogger | None = None,
    ):
        self.client = client
        self.dry_run = dry_run
        self.magic = magic
        self.deviation_points = deviation_points
        self.event_logger = event_logger or NullEventLogger()
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
        intended_volume = self._compute_volume(signal, account_balance, risk_pct)
        if intended_volume <= 0:
            logger.warning(f"Volume 0 para señal {signal.symbol} — descartada")
            self.event_logger.order(
                strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
                ticket=None, signal_entry=signal.entry_price, signal_sl=signal.stop_loss,
                signal_tp=signal.take_profit, fill_price=None, volume=0.0,
                intended_volume=intended_volume, slippage_pips=None, retcode=None,
                comment="reject:zero_volume",
            )
            return None

        volume = self._round_to_lot_step(signal.symbol, intended_volume)
        if volume <= 0:
            logger.warning(f"Volume ajustado a lote mínimo resultó 0 — descartada")
            self.event_logger.order(
                strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
                ticket=None, signal_entry=signal.entry_price, signal_sl=signal.stop_loss,
                signal_tp=signal.take_profit, fill_price=None, volume=0.0,
                intended_volume=intended_volume, slippage_pips=None, retcode=None,
                comment="reject:rounded_to_zero",
            )
            return None

        if self.dry_run:
            ticket = self._fake_ticket()
            logger.info(
                f"[DRY-RUN] OPEN {signal.side.value} {signal.symbol} "
                f"vol={volume:.2f} @ {signal.entry_price:.5f} "
                f"SL={signal.stop_loss:.5f} TP={signal.take_profit:.5f} "
                f"strategy={strategy_id} ticket={ticket}"
            )
            self.event_logger.order(
                strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
                ticket=ticket, signal_entry=signal.entry_price, signal_sl=signal.stop_loss,
                signal_tp=signal.take_profit, fill_price=signal.entry_price, volume=volume,
                intended_volume=intended_volume, slippage_pips=0.0, retcode=10009,
                comment="dry_run",
            )
            return ticket

        return self._send_market_order(signal, volume, intended_volume, strategy_id)

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

        # Validate minimum stop distance required by the broker.
        # MT5 retcode 10016 (Invalid stops) fires when SL is within stops_level
        # points of the current bid/ask. Skip the modify silently — the trail will
        # retry on the next bar when price has moved further away.
        info = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        if info is not None and tick is not None:
            min_distance = info.trade_stops_level * info.point
            if p.type == mt5.POSITION_TYPE_BUY:
                if new_sl >= tick.bid - min_distance:
                    logger.debug(
                        f"MODIFY skip ticket={ticket}: SL {new_sl:.5f} too close to bid "
                        f"{tick.bid:.5f} (min dist={min_distance:.5f})"
                    )
                    return False
            else:
                if new_sl <= tick.ask + min_distance:
                    logger.debug(
                        f"MODIFY skip ticket={ticket}: SL {new_sl:.5f} too close to ask "
                        f"{tick.ask:.5f} (min dist={min_distance:.5f})"
                    )
                    return False

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

    def _send_market_order(
        self, signal: Signal, volume: float, intended_volume: float, strategy_id: str
    ) -> Optional[int]:
        self.client.ensure_connected()
        mt5 = self.client.raw
        tick = mt5.symbol_info_tick(signal.symbol)
        if tick is None:
            logger.error(f"Sin tick para {signal.symbol}")
            self.event_logger.order(
                strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
                ticket=None, signal_entry=signal.entry_price, signal_sl=signal.stop_loss,
                signal_tp=signal.take_profit, fill_price=None, volume=volume,
                intended_volume=intended_volume, slippage_pips=None, retcode=None,
                comment="reject:no_tick",
            )
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
            "comment": f"strat:{strategy_id[:32]}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)

        # Compute slippage in points (raw price diff in symbol's quote unit).
        # Positive slippage = adverse (worse fill than signal price).
        if signal.side == Side.LONG:
            slippage_raw = price - signal.entry_price
        else:
            slippage_raw = signal.entry_price - price
        info = mt5.symbol_info(signal.symbol)
        point = float(info.point) if info is not None else 0.00001
        slippage_pips = slippage_raw / point if point > 0 else None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                f"OPEN fallo {signal.symbol} retcode={result.retcode} comment={result.comment}"
            )
            self.event_logger.order(
                strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
                ticket=None, signal_entry=signal.entry_price, signal_sl=signal.stop_loss,
                signal_tp=signal.take_profit, fill_price=price, volume=volume,
                intended_volume=intended_volume, slippage_pips=slippage_pips,
                retcode=int(result.retcode), comment=str(result.comment),
                bid_at_send=float(tick.bid), ask_at_send=float(tick.ask),
            )
            return None
        logger.info(
            f"OPEN OK ticket={result.order} {signal.side.value} {signal.symbol} "
            f"vol={volume} @ {price} SL={signal.stop_loss} TP={signal.take_profit}"
        )
        self.event_logger.order(
            strategy_id=strategy_id, symbol=signal.symbol, side=signal.side.value,
            ticket=int(result.order), signal_entry=signal.entry_price,
            signal_sl=signal.stop_loss, signal_tp=signal.take_profit,
            fill_price=price, volume=volume, intended_volume=intended_volume,
            slippage_pips=slippage_pips, retcode=int(result.retcode),
            comment=f"strat:{strategy_id[:32]}",
            bid_at_send=float(tick.bid), ask_at_send=float(tick.ask),
        )
        return int(result.order)

    def _compute_volume(self, signal: Signal, balance: float, risk_pct: float) -> float:
        if self.client.fake:
            # Backtest/test mode: raw units are self-consistent, no currency conversion needed.
            return size_by_fixed_risk(balance, risk_pct, signal.entry_price, signal.stop_loss)

        # Real MT5 connection (live or dry-run with real data).
        # Use trade_tick_value which MT5 expresses in account currency (EUR) and already
        # incorporates the quote-to-account conversion. Without this, JPY pairs (GBPJPY,
        # USDJPY) produce lot sizes ~160× too small and get capped at the lot minimum.
        self.client.ensure_connected()
        info = self.client.raw.symbol_info(signal.symbol)
        risk_amount = balance * risk_pct
        stop_distance = abs(signal.entry_price - signal.stop_loss)
        if stop_distance == 0 or info is None:
            return 0.0
        tick_size = info.trade_tick_size
        tick_value = info.trade_tick_value  # account-currency per tick per 1 lot
        if tick_size > 0 and tick_value > 0:
            return risk_amount / ((stop_distance / tick_size) * tick_value)
        # Fallback for symbols without tick data (old formula).
        contract_size = info.trade_contract_size or 100_000
        return size_by_fixed_risk(balance, risk_pct, signal.entry_price, signal.stop_loss) / contract_size

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
