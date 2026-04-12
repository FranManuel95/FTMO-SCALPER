# backtest/run_usdjpy_b.py — Runner Estrategia B: USDJPY NY Continuation
#
# Ejecutar:  python -m backtest.run_usdjpy_b
#
# Qué hace:
#   1. Corre la Estrategia B con parámetros base
#   2. Muestra métricas FTMO
#   3. Guarda trades y resumen mensual en backtest/results/

from pathlib import Path
import pandas as pd
from backtest.backtester_usdjpy_b import USDJPYBacktesterB


def run(params: dict | None = None) -> None:
    bt = USDJPYBacktesterB(
        initial_balance=10000,
        risk_per_trade=0.005,
        symbol="USDJPY",
    )

    # Parámetros base — ajustar después del primer backtest
    if params:
        for k, v in params.items():
            setattr(bt, k, v)

    result = bt.run()

    print("\n=== RESULTADO USDJPY - ESTRATEGIA B (NY Continuation) ===")
    print(f"Total trades:   {result.total_trades}")
    print(f"Win rate:       {result.win_rate:.2%}")
    print(f"Profit factor:  {result.profit_factor:.3f}  (mín FTMO: 1.3)")
    print(f"Sharpe:         {result.sharpe_ratio:.3f}  (mín FTMO: 1.5)")
    print(f"Sortino:        {result.sortino_ratio:.3f}")
    print(f"Max drawdown:   {result.max_drawdown:.2%}  (máx FTMO: 8%)")
    print(f"Total return:   {result.total_return:.2%}")
    print(f"Avg win:        ${result.avg_win:.2f}")
    print(f"Avg loss:       ${result.avg_loss:.2f}")
    print(f"Expectancy:     ${result.expectancy:.2f}")
    print(f"FTMO OK:        {'✓ SÍ' if result.passes_ftmo_filter() else '✗ NO'}")

    if hasattr(result, "extra_stats") and result.extra_stats:
        print("\n=== SALIDAS ===")
        for k, v in result.extra_stats.items():
            print(f"  {k}: {v}")

    if not bt.last_trades_detail:
        print("\n[!] Sin trades — revisa los filtros o el dataset")
        return

    out_dir = Path("backtest/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    trades_df = pd.DataFrame(bt.last_trades_detail)
    trades_df.to_csv(out_dir / "usdjpy_b_trades.csv", index=False)
    print(f"\nTrades → backtest/results/usdjpy_b_trades.csv")

    # Resumen mensual
    trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
    trades_df["month"] = trades_df["entry_time"].dt.to_period("M").astype(str)
    monthly = (
        trades_df.groupby("month")
        .agg(
            trades   = ("pnl", "count"),
            wins     = ("won", lambda s: int(s.sum())),
            pnl      = ("pnl", "sum"),
            avg_pnl  = ("pnl", "mean"),
            tp       = ("exit_reason", lambda s: int((s == "tp").sum())),
            sl       = ("exit_reason", lambda s: int((s == "sl").sum())),
            timeout  = ("exit_reason", lambda s: int((s == "timeout").sum())),
        )
        .reset_index()
    )
    monthly["win_rate"] = monthly["wins"] / monthly["trades"]
    monthly.to_csv(out_dir / "usdjpy_b_monthly.csv", index=False)

    print("\n=== RESUMEN MENSUAL ===")
    print(monthly.to_string(index=False))

    # Racha de pérdidas
    streak = max_streak = 0
    for pnl in trades_df["pnl"]:
        streak = (streak + 1) if pnl < 0 else 0
        max_streak = max(max_streak, streak)
    print(f"\nMáxima racha pérdidas: {max_streak}")

    # Trades/día promedio
    daily_counts = trades_df.groupby(
        trades_df["entry_time"].dt.date
    )["pnl"].count()
    print(f"Trades/día promedio:   {daily_counts.mean():.2f}")
    print(f"Días con trades:       {len(daily_counts)}")


if __name__ == "__main__":
    run()
