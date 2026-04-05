# execution/mt4_bridge.py — Puente Python ↔ MetaTrader 4

import zmq
import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class AccountInfo:
    balance: float
    equity:  float
    margin:  float

class MT4Bridge:

    def __init__(self, push_port: int = 32768,
                 pull_port: int = 32769,
                 sub_port:  int = 32770):
        self.context = zmq.Context()
        self.push    = self.context.socket(zmq.PUSH)
        self.pull    = self.context.socket(zmq.PULL)
        self.push.connect(f"tcp://localhost:{push_port}")
        self.pull.connect(f"tcp://localhost:{pull_port}")
        self.pull.setsockopt(zmq.RCVTIMEO, 10000)
        self.log = logging.getLogger("MT4Bridge")

    def get_account_info(self) -> AccountInfo:
        self.push.send_string("TRADE;GET_ACCOUNT_INFO")
        resp_str = self.pull.recv_string()
        resp_str = resp_str.replace("'", '"')
        resp = json.loads(resp_str)
        data = resp["_data"][0]
        return AccountInfo(
            balance=float(data["account_balance"]),
            equity =float(data["account_equity"]),
            margin =float(data["account_free_margin"])
        )

    def get_candles(self, symbol: str = "EURUSD",
                    timeframe: int = 5, count: int = 100) -> list:
        end   = datetime.utcnow()
        start = end - timedelta(hours=count * timeframe // 60 + 2)
        cmd   = f"HIST;{symbol};{timeframe};{start.strftime('%Y.%m.%d %H:%M')};{end.strftime('%Y.%m.%d %H:%M')}"
        self.push.send_string(cmd)
        resp_str = self.pull.recv_string()
        resp_str = resp_str.replace("'", '"')
        resp = json.loads(resp_str)
        candles = []
        for c in resp.get("_data", []):
            candles.append({
                "time":  c["time"],
                "open":  float(c["open"]),
                "high":  float(c["high"]),
                "low":   float(c["low"]),
                "close": float(c["close"])
            })
        return candles

    def get_candles_history(self, symbol: str = "EURUSD",
                            timeframe: int = 5,
                            months: int = 6) -> list:
        all_candles = []
        end         = datetime.utcnow()
        chunk       = timedelta(days=7)
        start_total = end - timedelta(days=months * 30)
        current_end = end

        print(f"Descargando {months} meses de {symbol} M{timeframe}...")

        while current_end > start_total:
            current_start = max(current_end - chunk, start_total)
            cmd = (f"HIST;{symbol};{timeframe};"
                   f"{current_start.strftime('%Y.%m.%d %H:%M')};"
                   f"{current_end.strftime('%Y.%m.%d %H:%M')}")
            try:
                self.push.send_string(cmd)
                resp_str = self.pull.recv_string()
                resp_str = resp_str.replace("'", '"')
                resp = json.loads(resp_str)
                chunk_candles = []
                for c in resp.get("_data", []):
                    chunk_candles.append({
                        "time":  c["time"],
                        "open":  float(c["open"]),
                        "high":  float(c["high"]),
                        "low":   float(c["low"]),
                        "close": float(c["close"])
                    })
                all_candles = chunk_candles + all_candles
                print(f"  {current_start.strftime('%Y-%m-%d')} -> {current_end.strftime('%Y-%m-%d')}: {len(chunk_candles)} velas")
            except Exception as e:
                print(f"  Error en chunk: {e}")

            current_end = current_start
            time.sleep(0.2)

        print(f"Total: {len(all_candles)} velas descargadas")
        return all_candles

    def open_trade(self, symbol: str, order_type: str,
                   lots: float, sl: float, tp: float,
                   comment: str = "FTMO_BOT") -> dict:
        type_id = 0 if order_type == "BUY" else 1
        cmd = f"TRADE;OPEN;{type_id};{symbol};0;{sl};{tp};{comment};{lots};12345;0"
        self.push.send_string(cmd)
        resp_str = self.pull.recv_string()
        resp_str = resp_str.replace("'", '"')
        resp = json.loads(resp_str)
        ticket = resp.get("_ticket", -1)
        status = "OK" if ticket > 0 else "ERROR"
        self.log.info(f"Trade abierto: {resp}")
        return {"status": status, "ticket": ticket}

    def close_all(self):
        self.push.send_string("TRADE;CLOSE_ALL")
        return self.pull.recv_string()

    def disconnect(self):
        self.push.close()
        self.pull.close()
        self.context.term()