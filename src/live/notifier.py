"""
Notifier — envío de alertas a Telegram.

El runner delega todos los eventos operativos (señal, orden abierta, cierre,
guards, errores) a un notifier. `NullNotifier` es el default (no-op) para tests.
`TelegramNotifier` postea al Bot API con el token/chat_id del usuario.

No usamos python-telegram-bot ni httpx para no añadir dependencias: requests
ya está en pyproject y basta para un POST síncrono con timeout corto.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime

import requests

from src.core.types import Signal

from .order_manager import LivePosition

logger = logging.getLogger(__name__)


class Notifier:
    """Interfaz base — cualquier método puede no-opear."""

    def on_startup(self, balance: float, strategies: list[str]) -> None: ...
    def on_signal(self, strategy_id: str, sig: Signal) -> None: ...
    def on_order_opened(self, pos: LivePosition) -> None: ...
    def on_position_closed(self, pos: LivePosition, pnl: float) -> None: ...
    def on_guard_triggered(self, guard: str, reason: str) -> None: ...
    def on_error(self, context: str, err: str) -> None: ...
    def on_heartbeat(self, msg: str) -> None: ...


class NullNotifier(Notifier):
    """Default no-op — todo lo que recibe se ignora."""


@dataclass
class TelegramNotifier(Notifier):
    bot_token: str
    chat_id: str
    timeout_s: float = 10.0
    prefix: str = "FTMO"

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            logger.warning(
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID no definidos — "
                "desactivando notificaciones"
            )
            return None
        return cls(bot_token=token, chat_id=chat)

    # ── Envío básico ────────────────────────────────────────────────────────

    def _send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": f"[{self.prefix}] {text}",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=self.timeout_s)
            if not r.ok:
                logger.error(f"Telegram API {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.error(f"Telegram send falló: {e}")

    # ── Eventos operativos ──────────────────────────────────────────────────

    def on_startup(self, balance: float, strategies: list[str]) -> None:
        self._send(
            f"🟢 <b>Runner iniciado</b>\n"
            f"Balance: {balance:.2f}\n"
            f"Estrategias: {', '.join(strategies)}\n"
            f"{datetime.utcnow():%Y-%m-%d %H:%M UTC}"
        )

    def on_signal(self, strategy_id: str, sig: Signal) -> None:
        self._send(
            f"📡 <b>Señal</b> {strategy_id}\n"
            f"{sig.symbol} {sig.side.value} @ {sig.entry_price:.5f}\n"
            f"SL {sig.stop_loss:.5f} | TP {sig.take_profit:.5f}\n"
            f"ts {sig.timestamp:%Y-%m-%d %H:%M UTC}"
        )

    def on_order_opened(self, pos: LivePosition) -> None:
        self._send(
            f"🟢 <b>ORDEN ABIERTA</b> {pos.strategy_id}\n"
            f"#{pos.ticket} {pos.symbol} {pos.side.value} vol={pos.volume:.2f}\n"
            f"Entry {pos.entry_price:.5f} | SL {pos.stop_loss:.5f} | TP {pos.take_profit:.5f}"
        )

    def on_position_closed(self, pos: LivePosition, pnl: float) -> None:
        emoji = "✅" if pnl >= 0 else "🔴"
        self._send(
            f"{emoji} <b>CIERRE</b> {pos.strategy_id}\n"
            f"#{pos.ticket} {pos.symbol} {pos.side.value}\n"
            f"PnL: <b>{pnl:+.2f}</b>"
        )

    def on_guard_triggered(self, guard: str, reason: str) -> None:
        self._send(f"⛔ <b>GUARD {guard}</b>\n{reason}")

    def on_error(self, context: str, err: str) -> None:
        self._send(f"⚠️ <b>Error</b> en {context}\n<code>{err[:500]}</code>")

    def on_heartbeat(self, msg: str) -> None:
        self._send(f"💓 {msg}")
