# execution/mt4_bridge.py — Bridge MT5 via API nativa

import MetaTrader5 as mt5
import pandas as pd
import logging
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AccountInfo:
    balance: float
    equity:  float
    margin:  float

class MT4Bridge:

    def __init__(self, **kwargs):
        self.log = logging.getLogger("MT5Bridge")
        if not mt5.initialize():
            raise ConnectionError(f"Error inicializando MT5: {mt5.last_error()}")
        account = mt5.account_info()
        self.log.info(f"MT5 conectado | {account.login} | {account.company} | ${account.balance}")

    def get_account_info(self) -> AccountInfo:
        info = mt5.account_info()
        if info is None:
            raise ConnectionError(f"Error obteniendo cuenta: {mt5.last_error()}")
        return AccountInfo(
            balance=float(info.balance),
            equity =float(info.equity),
            margin =float(info.margin_free)
        )

    def get_candles(self, symbol: str = "EURUSD",
                    timeframe: int = 5,
                    count: int = 100) -> list:
        tf_map = {
            1:    mt5.TIMEFRAME_M1,
            5:    mt5.TIMEFRAME_M5,
            15:   mt5.TIMEFRAME_M15,
            30:   mt5.TIMEFRAME_M30,
            60:   mt5.TIMEFRAME_H1,
            240:  mt5.TIMEFRAME_H4,
            1440: mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            self.log.warning(f"Sin datos para {symbol} TF={timeframe}")
            return []
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'time':  str(row['time']),
                'open':  float(row['open']),
                'high':  float(row['high']),
                'low':   float(row['low']),
                'close': float(row['close'])
            })
        return candles

    def open_trade(self, symbol: str, order_type: str,
                   lots: float, sl: float, tp: float,
                   comment: str = "FTMO_BOT") -> dict:
        
         # --- AÑADIR ESTO ---
        term = mt5.terminal_info()
        self.log.info(
            f"Terminal: trade_allowed={term.trade_allowed} | "
            f"connected={term.connected} | "
            f"trade_expert={term.trade_expert}"
        )
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"status": "ERROR", "ticket": -1}

        if order_type == "BUY":
            price     = tick.ask
            order_t   = mt5.ORDER_TYPE_BUY
        else:
            price     = tick.bid
            order_t   = mt5.ORDER_TYPE_SELL

        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      symbol,
            "volume":      float(lots),
            "type":        order_t,
            "price":       price,
            "sl":          float(sl),
            "tp":          float(tp),
            "deviation":   10,
            "magic":       234000,
            "comment":     comment,
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            self.log.error(f"Error enviando orden: {mt5.last_error()}")
            return {"status": "ERROR", "ticket": -1}

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.log.info(f"Orden ejecutada: ticket={result.order}")
            return {"status": "OK", "ticket": result.order}
        else:
            self.log.error(f"Error en orden: {result.retcode} - {result.comment}")
            return {"status": "ERROR", "ticket": -1}

    def close_all(self):
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return "Sin posiciones abiertas"
        for pos in positions:
            if pos.type == mt5.ORDER_TYPE_BUY:
                price  = mt5.symbol_info_tick(pos.symbol).bid
                order_t = mt5.ORDER_TYPE_SELL
            else:
                price  = mt5.symbol_info_tick(pos.symbol).ask
                order_t = mt5.ORDER_TYPE_BUY
            request = {
                "action":   mt5.TRADE_ACTION_DEAL,
                "symbol":   pos.symbol,
                "volume":   pos.volume,
                "type":     order_t,
                "position": pos.ticket,
                "price":    price,
                "deviation": 10,
                "magic":    234000,
                "comment":  "CLOSE_ALL",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(request)
        return "Todas las posiciones cerradas"

    def disconnect(self):
        mt5.shutdown()
        self.log.info("MT5 desconectado")