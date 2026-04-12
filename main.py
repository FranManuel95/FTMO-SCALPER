# main.py — FTMO Scalper v3 — Multi-símbolo: EURUSD, GBPUSD, USDJPY, XAUUSD
#
# Arquitectura de estrategias:
#   MTF  (EURUSD, GBPUSD) → London + NY, EMA9/21 cross + pullback
#   BRK  (USDJPY, EURJPY) → [futuro] breakout rango asiático
#   ORB  (XAUUSD)         → [futuro] opening range breakout 07-09 UTC
#
# Límites FTMO activos:
#   - Pérdida diaria máxima : 4.5%  (límite real 5%)
#   - Drawdown total máximo : 9.5%  (límite real 10%)
#   - Riesgo por operación  : 0.5%
#   - Máximo operaciones/día: 8

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
from config.settings        import (
    SYMBOLS_MTF, HTF_UPDATE_INTERVAL_M5,
    MAIN_LOOP_SLEEP_SEC, BLOCK_WAIT_LONG_SEC, BLOCK_WAIT_SHORT_SEC,
)

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


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def fetch_dataframe(bridge: MT4Bridge, symbol: str,
                    timeframe: int, count: int) -> pd.DataFrame:
    candles = bridge.get_candles(symbol, timeframe=timeframe, count=count)
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles).set_index('time')
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def verify_autotrading(bridge: MT4Bridge) -> bool:
    """Verifica que MT5 tiene AutoTrading activo. Necesario para operar."""
    try:
        import MetaTrader5 as mt5
        info = mt5.terminal_info()
        return info is not None and info.trade_allowed
    except Exception:
        return False


# ─────────────────────────────────────────────
# BUCLE PRINCIPAL DE UN SÍMBOLO MTF
# ─────────────────────────────────────────────

def process_mtf_symbol(
    symbol: str,
    bridge: MT4Bridge,
    guardian: FTMORiskGuardian,
    engine: SignalEngine,
    htf_counter: dict,
    last_candle: dict,
) -> None:
    """
    Procesa un símbolo con la estrategia MTF (EURUSD/GBPUSD).
    - Obtiene velas 5M
    - Actualiza HTF (1H + 15M) cada ~1 hora
    - Analiza señal y ejecuta si es válida
    """
    df_5m = fetch_dataframe(bridge, symbol, timeframe=5, count=100)
    if df_5m.empty or len(df_5m) < 30:
        log.warning(f"{symbol}: Pocas velas 5M, saltando")
        return

    current_candle = df_5m.index[-1]
    if last_candle[symbol] != current_candle:
        last_candle[symbol] = current_candle
        htf_counter[symbol] += 1

    # Actualizar HTF cuando toca (cada hora aprox.) o al inicio
    if htf_counter[symbol] % HTF_UPDATE_INTERVAL_M5 == 1 or \
            engine._df_1h is None:
        df_15m = fetch_dataframe(bridge, symbol, timeframe=15, count=200)
        df_1h  = fetch_dataframe(bridge, symbol, timeframe=60, count=500)
        if df_15m.empty or df_1h.empty:
            log.warning(f"{symbol}: No se pudieron obtener HTF, saltando")
            return
        engine.update_higher_timeframes(df_1h, df_15m)
        log.info(f"{symbol}: HTF actualizados | 1H:{len(df_1h)} | 15M:{len(df_15m)} velas")

    # Analizar señal
    setup = engine.analyze(df_5m)
    if setup.signal == Signal.NONE:
        log.debug(f"{symbol}: Sin señal — {setup.reason}")
        return

    # Calcular lote y validar con guardian
    acct = bridge.get_account_info()
    lot  = guardian.calculate_lot_size(acct.balance, setup.sl_pips)

    log.info(
        f"{symbol}: SEÑAL {setup.signal.value} [{setup.entry_mode.value}] | "
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
        ticket = result['ticket']
        log.info(f"{symbol}: Trade abierto — Ticket: {ticket}")
        send_alert(
            f"*Trade Abierto*\n"
            f"Par: `{symbol}`\n"
            f"Dirección: `{setup.signal.value}`\n"
            f"Modo: `{setup.entry_mode.value}`\n"
            f"Lote: `{lot:.2f}`\n"
            f"Entry: `{setup.entry_price:.5f}`\n"
            f"SL: `{setup.stop_loss:.5f}`\n"
            f"TP: `{setup.take_profit:.5f}`\n"
            f"Razón: {setup.reason}\n"
            f"Ticket: `{ticket}`"
        )
    else:
        log.error(f"{symbol}: Error abriendo trade: {result}")
        send_alert(f"*ERROR* {symbol}: {result}")


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────

def main():
    account_size = float(os.getenv("FTMO_ACCOUNT_SIZE", 10000))
    active_symbols = SYMBOLS_MTF  # EURUSD + GBPUSD

    log.info(
        f"FTMO Scalper v3 iniciando | "
        f"Capital: ${account_size} | "
        f"Símbolos: {active_symbols}"
    )

    # ── Inicializar componentes ──
    guardian = FTMORiskGuardian(account_size)
    bridge   = MT4Bridge()

    if not verify_autotrading(bridge):
        msg = "AutoTrading desactivado en MT5. Actívalo y reinicia el bot."
        log.error(msg)
        send_alert(f"*ERROR CRÍTICO* {msg}")
        sys.exit(1)

    log.info("AutoTrading verificado: OK")

    news    = NewsFilter()
    engines = {sym: SignalEngine() for sym in active_symbols}

    htf_counter = {sym: 0    for sym in active_symbols}
    last_candle = {sym: None for sym in active_symbols}

    send_alert(
        f"*FTMO Scalper v3 iniciado*\n"
        f"Capital: `${account_size}`\n"
        f"Pares: `{', '.join(active_symbols)}`\n"
        f"Estrategia: MTF EMA9/21 (London + NY)\n"
        f"Entradas: Crossover + Pullback\n"
        f"Límites: DD 9.5% | Diario 4.5% | Riesgo 0.5%/trade"
    )

    acct = bridge.get_account_info()  # necesario para el bloque KeyboardInterrupt

    try:
        while True:
            try:
                # ── Estado global de cuenta ──
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
                    wait = BLOCK_WAIT_LONG_SEC \
                        if status in (TradingStatus.WEEKEND,
                                      TradingStatus.MAX_TRADES,
                                      TradingStatus.XMAS_BLOCK) \
                        else BLOCK_WAIT_SHORT_SEC
                    log.warning(f"BLOQUEADO: {status.value} → esperando {wait}s")
                    time.sleep(wait)
                    continue

                # ── Procesar cada símbolo MTF ──
                for symbol in active_symbols:
                    try:
                        process_mtf_symbol(
                            symbol     = symbol,
                            bridge     = bridge,
                            guardian   = guardian,
                            engine     = engines[symbol],
                            htf_counter= htf_counter,
                            last_candle= last_candle,
                        )
                    except Exception as e:
                        log.error(f"{symbol}: Error procesando par: {e}")

                time.sleep(MAIN_LOOP_SLEEP_SEC)

            except Exception as e:
                log.error(f"Error en bucle principal: {e}")
                time.sleep(BLOCK_WAIT_SHORT_SEC)

    except KeyboardInterrupt:
        log.info("Bot detenido manualmente")
        send_alert(
            f"*Bot detenido*\n"
            f"Trades hoy: `{guardian.trades_today}`\n"
            f"Equity final: `${acct.equity:.2f}`"
        )
        bridge.close_all()
        bridge.disconnect()


if __name__ == "__main__":
    main()
