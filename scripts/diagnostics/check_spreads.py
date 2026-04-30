"""Compara el spread real del broker con el modelado en backtest.

Correr en el PC Windows con MT5 abierto y el bot parado:
    python scripts/diagnostics/check_spreads.py

Hipótesis: si el spread real es >> al modelado, explica el patrón
de 0/33 trades alcanzando MFE > 1.5R en los últimos 4 días.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import MetaTrader5 as mt5


SYMBOLS = [
    ("XAUUSD",  35.0),
    ("EURUSD",   7.0),
    ("GBPUSD",   7.0),
    ("USDJPY",   7.0),
    ("EURJPY",   7.0),
    ("GBPJPY",   7.0),
    ("AUDUSD",   7.0),
    ("NZDUSD",   7.0),
    ("USDCAD",   7.0),
    ("USDCHF",   7.0),
    ("EURGBP",   7.0),
]


def pip_size(symbol: str) -> float:
    if symbol == "XAUUSD":
        return 0.10  # XAUUSD: 1 pip = $0.10
    if "JPY" in symbol:
        return 0.01
    return 0.0001


def main() -> None:
    if not mt5.initialize():
        print(f"mt5.initialize() falló: {mt5.last_error()}")
        return

    info = mt5.account_info()
    print(f"Account: {info.login} | Balance: {info.balance} {info.currency} | Server: {info.server}")
    print()

    print(f"{'Symbol':10s} {'Bid':>12s} {'Ask':>12s} {'Spread (pts)':>14s} {'Spread (pips)':>14s} {'Backtest cost ($/lot)':>22s}")
    print("-" * 88)

    for symbol, modeled_cost in SYMBOLS:
        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            print(f"{symbol:10s} (no info — símbolo no disponible en este broker)")
            continue

        if not sym_info.visible:
            mt5.symbol_select(symbol, True)
            time.sleep(0.2)

        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.bid == 0:
            print(f"{symbol:10s} (sin tick — mercado cerrado?)")
            continue

        spread_pts = tick.ask - tick.bid
        spread_pips = spread_pts / pip_size(symbol)

        print(f"{symbol:10s} {tick.bid:12.5f} {tick.ask:12.5f} {spread_pts:14.5f} {spread_pips:14.2f} {modeled_cost:22.2f}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
