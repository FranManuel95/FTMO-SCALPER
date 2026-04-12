# backtest/filter_usdjpy_ftmo_candidates.py

import pandas as pd

df = pd.read_csv("backtest/results/usdjpy_m5_global_grid_results.csv")

filtered = df[
    (df["total_trades"] >= 30) &
    (df["profit_factor"] >= 1.20) &
    (df["max_drawdown"] <= 0.07) &
    (df["win_rate"] >= 0.35) &
    (df["expectancy"] > 0)
].copy()

filtered = filtered.sort_values(
    by=["score_ftmo", "profit_factor", "total_return"],
    ascending=False
)

print(filtered.head(20).to_string(index=False))

filtered.to_csv(
    "backtest/results/usdjpy_m5_ftmo_candidates.csv",
    index=False
)