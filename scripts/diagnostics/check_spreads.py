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

from src.live.mt5_client import MT5Client


SYMBOLS = [
    ("XAUUSD",  35.0,  "$/lot round-trip"),
    ("EURUSD",   7.0,  "$/lot round-trip"),
    ("GBPUSD",   7.0,  "$/lot round-trip"),
    ("USDJPY",   7.0,  "$/lot round-trip"),
    ("EURJPY",   7.0,  "$/lot round-trip"),
    ("GBPJPY",   7.0,  "$/lot round-trip"),
    ("AUDUSD",   7.0,  "$/lot round-trip"),
    ("NZDUSD",   7.0,  "$/lot round-trip"),
    ("USDCAD",   7.0,  "$/lot round-trip"),
    ("USDCHF",   7.0,  "$/lot round-trip"),
    ("EURGBP",   7.0,  "$/lot round-trip"),
]


def main() -> None:
    client = MT5Client()
    client.connect()

    print(f"{'Symbol':10s} {'Bid':>12s} {'Ask':>12s} {'Spread (pts)':>14s} {'Spread (pips)':>14s} {'Backtest cost':>14s}")
    print("-" * 80)

    for symbol, modeled_cost, _unit in SYMBOLS:
        info = client.raw.symbol_info(symbol)
        if info is None:
            print(f"{symbol:10s} (no info)")
            continue

        # Asegura que el símbolo está en Market Watch
        if not info.visible:
            client.raw.symbol_select(symbol, True)
            time.sleep(0.2)

        tick = client.raw.symbol_info_tick(symbol)
        if tick is None:
            print(f"{symbol:10s} (sin tick)")
            continue

        spread_points = tick.ask - tick.bid
        # pip size: para JPY 0.01, demás 0.0001, XAU 0.01
        if symbol == "XAUUSD":
            pip = 0.01
        elif "JPY" in symbol:
            pip = 0.01
        else:
            pip = 0.0001
        spread_pips = spread_points / pip

        print(f"{symbol:10s} {tick.bid:12.5f} {tick.ask:12.5f} {spread_points:14.5f} {spread_pips:14.2f} {modeled_cost:14.2f}")

    client.shutdown()


if __name__ == "__main__":
    main()
