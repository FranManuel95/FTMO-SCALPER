from pathlib import Path
import pandas as pd

from backtest.backtester_usdjpy import USDJPYBacktester


def main():
    bt = USDJPYBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.40,
        symbol="USDJPY"
    )

    # Parámetros finales del candidato A
    bt.BUFFER_PIPS = 0.04
    bt.MIN_BODY_RATIO = 0.50
    bt.MAX_BARS_IN_TRADE = 42
    bt.ADX_MIN = 12
    bt.ADX_MAX = 50
    bt.ATR_MIN = 0.020
    bt.SESSION_START = 7
    bt.SESSION_END = 16
    bt.ASIA_START = 0
    bt.ASIA_END = 7
    bt.MAX_TRADES_DAY = 1
    bt.BREAK_EVEN_R = 999.0

    result = bt.run()

    print("\n=== RESULTADO FINAL USDJPY - ESTRATEGIA A ===")
    print(f"Total trades:   {result.total_trades}")
    print(f"Winning trades: {result.winning_trades}")
    print(f"Losing trades:  {result.losing_trades}")
    print(f"Win rate:       {result.win_rate:.2%}")
    print(f"Profit factor:  {result.profit_factor}")
    print(f"Sharpe:         {result.sharpe_ratio}")
    print(f"Sortino:        {result.sortino_ratio}")
    print(f"Max drawdown:   {result.max_drawdown:.2%}")
    print(f"Total return:   {result.total_return:.2%}")
    print(f"Avg win:        {result.avg_win}")
    print(f"Avg loss:       {result.avg_loss}")
    print(f"Expectancy:     {result.expectancy}")

    if hasattr(result, "extra_stats") and result.extra_stats:
        print("\n=== EXIT REASONS ===")
        for k, v in result.extra_stats.items():
            print(f"{k}: {v}")

    out_dir = Path("backtest/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = pd.DataFrame(bt.last_trades_detail)
    trades_file = out_dir / "usdjpy_strategy_a_trades.csv"
    trades.to_csv(trades_file, index=False)

    print(f"\nTrades guardados en: {trades_file}")

    if not trades.empty:
        trades["entry_time"] = pd.to_datetime(trades["entry_time"])
        trades["month"] = trades["entry_time"].dt.to_period("M").astype(str)

        monthly = (
            trades.groupby("month")
            .agg(
                trades=("pnl", "count"),
                wins=("won", lambda s: int(s.sum())),
                pnl=("pnl", "sum"),
                avg_pnl=("pnl", "mean"),
                tp=("exit_reason", lambda s: int((s == "tp").sum())),
                sl=("exit_reason", lambda s: int((s == "sl").sum())),
                timeout=("exit_reason", lambda s: int((s == "timeout").sum())),
                breakeven=("exit_reason", lambda s: int((s == "breakeven").sum())),
            )
            .reset_index()
        )

        monthly["win_rate"] = monthly["wins"] / monthly["trades"]

        monthly_file = out_dir / "usdjpy_strategy_a_monthly.csv"
        monthly.to_csv(monthly_file, index=False)

        print("\n=== RESUMEN MENSUAL ===")
        print(monthly.to_string(index=False))
        print(f"\nResumen mensual guardado en: {monthly_file}")

        max_losing_streak = 0
        current_losing_streak = 0

        for pnl in trades["pnl"]:
            if pnl < 0:
                current_losing_streak += 1
                max_losing_streak = max(max_losing_streak, current_losing_streak)
            else:
                current_losing_streak = 0

        print(f"\nMáxima racha de pérdidas: {max_losing_streak}")


if __name__ == "__main__":
    main()