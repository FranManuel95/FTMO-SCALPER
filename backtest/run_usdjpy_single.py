from backtest.backtester_usdjpy import USDJPYBacktester


def main():
    bt = USDJPYBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.3,
        symbol="USDJPY"
    )

    result = bt.run()

    print("\n=== RESULTADO USDJPY BASE ===")
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

    if hasattr(result, "extra_stats"):
        print("\n=== EXIT REASONS ===")
        for k, v in result.extra_stats.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()