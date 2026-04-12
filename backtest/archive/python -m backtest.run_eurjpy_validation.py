import os
import pandas as pd
import numpy as np

from backtest.backtester_xau_m5 import XAUBacktesterM5


def run_dynamic_hold_test():
    """
    Test:
    - Horas activas: 9 y 15
    - Hold distinto por hora:
        9  -> 12 barras
        15 -> 24 barras
    """

    HOURS_SET = {9, 15}
    HOLD_BY_HOUR = {
        9: 12,
        15: 24,
    }

    bt = XAUBacktesterM5()

    print("=" * 90)
    print("TEST XAU M5 | HORAS 9_15 | HOLD DINÁMICO POR HORA")
    print("=" * 90)
    print(f"Horas activas: {sorted(HOURS_SET)}")
    print(f"Hold por hora: {HOLD_BY_HOUR}")

    result = bt.run(hours_set=HOURS_SET, hold_by_hour=HOLD_BY_HOUR)

    print("\n=== RESULTADO HOLD DINÁMICO ===")
    print(f"Trades:        {result['trades']}")
    print(f"Win rate:      {result['win_rate']:.2f}%")
    print(f"Profit factor: {result['profit_factor']:.3f}")
    print(f"Sharpe:        {result['sharpe']}")
    print(f"Sortino:       {result['sortino']}")
    print(f"Max DD %:      {result['max_dd_pct']:.2f}")
    print(f"Return %:      {result['total_return_pct']:.2f}")
    print(f"Avg win:       {result['avg_win']}")
    print(f"Avg loss:      {result['avg_loss']}")
    print(f"Expectancy:    {result['expectancy']}")
    print(f"Verdicto:      {result.get('verdict', 'N/A')}")
    print(f"Score:         {result.get('score', 'N/A')}")

    print("\n=== EXIT REASONS ===")
    print(result["exit_reason_counter"])

    if "trades_csv" in result:
        print(f"\nCSV trades: {result['trades_csv']}")

    return result


if __name__ == "__main__":
    run_dynamic_hold_test()