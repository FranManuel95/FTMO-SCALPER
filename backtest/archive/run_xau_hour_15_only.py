import os
import pandas as pd

from backtest.backtester_xau_m5 import XAUBacktesterM5


def run_hour_15_only():
    HOURS_SET = {15}

    bt = XAUBacktesterM5()
    bt.run_label = "hours_15_only"

    print("=" * 90)
    print("TEST XAU M5 | HORA 15 SOLO")
    print("=" * 90)
    print(f"Horas activas: {sorted(HOURS_SET)}")

    result = bt.run(hours_set=HOURS_SET)
    diag = bt.last_diagnostics or {}

    print("\n=== RESULTADO HORA 15 ===")
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
    run_hour_15_only()