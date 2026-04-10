from backtest.backtester_gbp import GBPBacktester

bt = GBPBacktester(
    initial_balance=10000,
    risk_per_trade=0.005,
    rr_ratio=1.4,
    symbol="GBPUSD",
    export_trades=True,
)

result = bt.run()

print("\n=== RESULTADO GBPUSD ===")
print(f"Total trades:   {result.total_trades}")
print(f"Winning trades: {result.winning_trades}")
print(f"Losing trades:  {result.losing_trades}")
print(f"Win rate:       {result.win_rate * 100:.2f}%")
print(f"Profit factor:  {result.profit_factor}")
print(f"Sharpe:         {result.sharpe_ratio}")
print(f"Sortino:        {result.sortino_ratio}")
print(f"Max drawdown:   {result.max_drawdown * 100:.2f}%")
print(f"Total return:   {result.total_return * 100:.2f}%")
print(f"Avg win:        {result.avg_win}")
print(f"Avg loss:       {result.avg_loss}")
print(f"Expectancy:     {result.expectancy}")