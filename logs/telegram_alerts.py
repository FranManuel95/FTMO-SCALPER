# logs/telegram_alerts.py — Alertas Telegram

import requests
import logging
import os

log = logging.getLogger("Telegram")

def send_alert(message: str):
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log.warning("Telegram no configurado")
        return

    try:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "Markdown"
        }, timeout=10)

        if resp.status_code == 200:
            log.info("Alerta Telegram enviada")
        else:
            log.error(f"Error Telegram: {resp.text}")

    except Exception as e:
        log.error(f"Error enviando alerta: {e}")