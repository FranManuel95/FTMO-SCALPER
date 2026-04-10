# main.py — FTMO Scalper MTF v2 — EURUSD + GBPUSD

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
    level    = logging.INFO,
    format   = '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers = [
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("MAIN")

HTF_UPDATE_INTERVAL = 12  # cada 12 velas M5 = 1 hora

SYMBOLS = ["EURUSD", "GBPUSD"]

def fetch_dataframe(bridge: MT4Bridge, symbol: str,
                    timeframe: int, count: int) -> pd.DataFrame:
    candles = bridge.get_candles(symbol, timeframe=timeframe, count=count)
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df = df.set_index('time')
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


def main():
    account_size = float(os.getenv("FTMO_ACCOUNT_SIZE", 10000))
    log.info(f"FTMO Scalper MTF v2 iniciando | Capital: ${account_size} | Pares: {SYMBOLS}")

    send_alert(
        f"*FTMO Scalper MTF v2 iniciado*\n"
        f"Capital: ${account_size}\n"
        f"Pares: {', '.join(SYMBOLS)}\n"
        f"EURUSD: MTF ADX+VWAP+Trailing\n"
        f"GBPUSD: SuperTrend+Regimen\n"
        f"Filtro navideño: 20 Dic - 3 Ene\n"
        f"Esperando apertura de mercado..."
    )

    guardian = FTMORiskGuardian(account_size)
    bridge   = MT4Bridge()

    import MetaTrader5 as mt5
    info = mt5.terminal_info()
    if info is None or not info.trade_allowed:
        log.error("AutoTrading desactivado en MT5. Activalo y reinicia el bot.")
        send_alert("*ERROR CRITICO* AutoTrading desactivado en MT5. Activalo manualmente.")
        sys.exit(1)

    log.info("AutoTrading verificado: OK")

    
    news     = NewsFilter()

    # Motor de señales por par
    engines = {symbol: SignalEngine() for symbol in SYMBOLS}

    # Contadores HTF por par
    htf_counters   = {symbol: 0 for symbol in SYMBOLS}
    last_candles   = {symbol: None for symbol in SYMBOLS}

    log.info("Conexion MT5 establecida")

    try:
        while True:
            try:
                # 1. Info de cuenta
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
                    wait = 300 if status.value in [
                        "WEEKEND_BLOCK", "MAX_DAILY_TRADES", "XMAS_BLOCK"
                    ] else 60
                    log.warning(f"BLOQUEADO: {status.value} -> esperando {wait}s")
                    time.sleep(wait)
                    continue

                # 2. Procesar cada par
                for symbol in SYMBOLS:
                    try:
                        # Obtener velas 5M
                        df_5m = fetch_dataframe(bridge, symbol, timeframe=5, count=100)
                        if df_5m.empty or len(df_5m) < 30:
                            log.warning(f"{symbol}: Pocas velas 5M")
                            continue

                        # Actualizar HTF cada hora
                        current_candle = df_5m.index[-1]
                        if last_candles[symbol] != current_candle:
                            last_candles[symbol] = current_candle
                            htf_counters[symbol] += 1

                        engine = engines[symbol]
                        if htf_counters[symbol] % HTF_UPDATE_INTERVAL == 1 \
                                or engine._df_1h is None:
                            df_15m = fetch_dataframe(bridge, symbol, timeframe=15, count=200)
                            df_1h  = fetch_dataframe(bridge, symbol, timeframe=60, count=500)
                            if not df_15m.empty and not df_1h.empty:
                                engine.update_higher_timeframes(df_1h, df_15m)
                                log.info(f"{symbol}: HTF actualizados | "
                                         f"1H:{len(df_1h)} | 15M:{len(df_15m)} velas")
                            else:
                                log.warning(f"{symbol}: No se pudieron obtener HTF")
                                continue

                        # Analizar señal
                        setup = engine.analyze(df_5m)

                        if setup.signal == Signal.NONE:
                            log.info(f"{symbol}: Sin señal — {setup.reason}")
                            continue

                        # Calcular lote y ejecutar
                        lot = guardian.calculate_lot_size(acct.balance, setup.sl_pips)
                        log.info(
                            f"{symbol}: SEÑAL {setup.signal.value} | "
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
                            log.info(f"{symbol}: Trade abierto. Ticket: {result['ticket']}")
                            send_alert(
                                f"*Trade Abierto*\n"
                                f"Par: {symbol}\n"
                                f"Dirección: {setup.signal.value}\n"
                                f"Lote: {lot:.2f}\n"
                                f"Entry: {setup.entry_price:.5f}\n"
                                f"SL: {setup.stop_loss:.5f}\n"
                                f"TP: {setup.take_profit:.5f}\n"
                                f"Razón: {setup.reason}\n"
                                f"Ticket: {result['ticket']}"
                            )
                        else:
                            log.error(f"{symbol}: Error abriendo trade: {result}")
                            send_alert(f"*ERROR* {symbol}: {result}")

                    except Exception as e:
                        log.error(f"{symbol}: Error procesando par: {e}")
                        continue

                time.sleep(30)

            except Exception as e:
                log.error(f"Error en bucle principal: {e}")
                time.sleep(60)

    except KeyboardInterrupt:
        log.info("Bot detenido manualmente")
        send_alert(
            f"*Bot detenido*\n"
            f"Trades hoy: {guardian.trades_today}\n"
            f"Equity final: ${acct.equity:.2f}"
        )
        bridge.close_all()
        bridge.disconnect()


if __name__ == "__main__":
    main()