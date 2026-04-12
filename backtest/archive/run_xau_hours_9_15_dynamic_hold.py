import os
import pandas as pd

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
    bt.run_label = "hours_9_15_dynamic_hold_9_12_15_24"

    print("=" * 90)
    print("TEST XAU M5 | HORAS 9_15 | HOLD DINÁMICO POR HORA")
    print("=" * 90)
    print(f"Horas activas: {sorted(HOURS_SET)}")
    print(f"Hold por hora: {HOLD_BY_HOUR}")

    result = bt.run(hours_set=HOURS_SET, hold_by_hour=HOLD_BY_HOUR)
    diag = bt.last_diagnostics or {}

    print("\n=== RESULTADO HOLD DINÁMICO ===")
    print(f"Trades:        {result.total_trades}")
    print(f"Win rate:      {result.win_rate * 100:.2f}%")
    print(f"Profit factor: {result.profit_factor}")
    print(f"Sharpe:        {result.sharpe_ratio}")
    print(f"Sortino:       {result.sortino_ratio}")
    print(f"Max DD %:      {result.max_drawdown * 100:.2f}")
    print(f"Return %:      {result.total_return * 100:.2f}")
    print(f"Avg win:       {result.avg_win}")
    print(f"Avg loss:      {result.avg_loss}")
    print(f"Expectancy:    {result.expectancy}")

    print("\n=== EXIT REASONS ===")
    print(diag.get("exit_reason_counter", {}))

    print("\n=== SIDE STATS ===")
    print(diag.get("sell_stats", {}))

    trades_csv = diag.get("trades_csv")
    if trades_csv:
        print(f"\nCSV trades: {trades_csv}")

        if os.path.exists(trades_csv):
            try:
                df = pd.read_csv(trades_csv)
                print("\n=== MUESTRA TRADES ===")
                print(df.head(20).to_string(index=False))
            except Exception as e:
                print(f"No se pudo leer el CSV: {e}")

    return result, diag


if __name__ == "__main__":
    run_dynamic_hold_test()