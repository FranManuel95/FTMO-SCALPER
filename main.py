# main.py — Orquestador principal FTMO Scalper con Telegram

import time
import logging
import os
import sys
import pandas as pd
from dotenv import load_dotenv
from risk.guardian          import FTMORiskGuardian, TradingStatus
from strategy.signal_engine import SignalEngine, Signal
from execution.mt4_bridge   import MT4Bridge
from data.news_filter       import NewsFilter
from logs.telegram_alerts   import send_alert

load_dotenv()

logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers= [
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("MAIN")

def main():
    account_size = float(os.getenv("FTMO_ACCOUNT_SIZE", 10000))
    symbol       = os.getenv("SYMBOL", "EURUSD")

    log.info(f"FTMO Scalper iniciando | Capital: ${account_size} | Par: {symbol}")
    send_alert(f"*FTMO Scalper iniciado*\nCapital: ${account_size}\nPar: {symbol}\nEsperando apertura de mercado...")

    guardian = FTMORiskGuardian(account_size)
    engine   = SignalEngine()
    bridge   = MT4Bridge()
    news     = NewsFilter()

    log.info("Conexion MT4 establecida")

    try:
        while True:
            try:
                acct        = bridge.get_account_info()
                news_active = news.is_news_active()
                status      = guardian.can_trade(acct.equity, news_active)
                report      = guardian.get_status_report(acct.equity)

                log.info(
                    f"[{status.value}] Equity:${acct.equity:.0f} | "
                    f"Loss:{report['daily_loss_pct']:.2f}% | "
                    f"DD:{report['total_dd_pct']:.2f}% | "
                    f"Trades:{report['trades_today']}/{guardian.MAX_TRADES_PER_DAY} | "
                    f"News:{'ACTIVAS' if news_active else 'OK'}"
                )

                if status != TradingStatus.ALLOWED:
                    wait = 300 if status.value in ["WEEKEND_BLOCK", "MAX_DAILY_TRADES"] else 60
                    log.warning(f"BLOQUEADO: {status.value} -> esperando {wait}s")
                    time.sleep(wait)
                    continue

                candles = bridge.get_candles(symbol, timeframe=5, count=100)
                if len(candles) < 30:
                    log.warning("Pocas velas recibidas, esperando...")
                    time.sleep(60)
                    continue

                df    = pd.DataFrame(candles)
                setup = engine.analyze(df)

                if setup.signal == Signal.NONE:
                    log.info(f"Sin senal: {setup.reason}")
                    time.sleep(30)
                    continue

                lot = guardian.calculate_lot_size(acct.balance, setup.sl_pips)
                log.info(
                    f"SENAL {setup.signal.value} | "
                    f"Lote:{lot:.2f} | SL:{setup.stop_loss:.5f} | "
                    f"TP:{setup.take_profit:.5f} | {setup.reason}"
                )

                result = bridge.open_trade(
                    symbol     = symbol,
                    order_type = setup.signal.value,
                    lots       = lot,
                    sl         = setup.stop_loss,
                    tp         = setup.take_profit
                )

                if result.get("status") == "OK":
                    guardian.register_trade()
                    log.info(f"Trade abierto. Ticket: {result['ticket']}")
                    send_alert(
                        f"*Trade Abierto*\n"
                        f"Par: {symbol}\n"
                        f"Direccion: {setup.signal.value}\n"
                        f"Lote: {lot:.2f}\n"
                        f"Entry: {setup.entry_price:.5f}\n"
                        f"SL: {setup.stop_loss:.5f}\n"
                        f"TP: {setup.take_profit:.5f}\n"
                        f"Ticket: {result['ticket']}"
                    )
                else:
                    log.error(f"Error abriendo trade: {result}")
                    send_alert(f"*ERROR* abriendo trade: {result}")

                time.sleep(300)

            except Exception as e:
                log.error(f"Error en bucle principal: {e}")
                time.sleep(60)

    except KeyboardInterrupt:
        log.info("Bot detenido manualmente")
        send_alert("*Bot detenido manualmente*")
        bridge.close_all()
        bridge.disconnect()

if __name__ == "__main__":
    main()