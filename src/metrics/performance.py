from typing import Sequence

import numpy as np
import pandas as pd

from src.core.types import Trade


def profit_factor(trades: Sequence[Trade]) -> float:
    wins = sum(t.pnl for t in trades if t.pnl > 0)
    losses = abs(sum(t.pnl for t in trades if t.pnl < 0))
    return wins / losses if losses > 0 else float("inf")


def win_rate(trades: Sequence[Trade]) -> float:
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.pnl > 0) / len(trades)


def expectancy(trades: Sequence[Trade]) -> float:
    if not trades:
        return 0.0
    return sum(t.pnl for t in trades) / len(trades)


def sharpe_ratio(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    returns = equity_curve.pct_change().dropna()
    if returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * np.sqrt(periods_per_year)


def equity_curve(trades: Sequence[Trade], initial_balance: float = 10000.0) -> pd.Series:
    if not trades:
        return pd.Series([initial_balance])
    closed = sorted([t for t in trades if t.exit_time is not None], key=lambda t: t.exit_time)
    times = [t.exit_time for t in closed]
    pnls = [t.pnl for t in closed]
    balance = initial_balance + pd.Series(pnls, index=times).cumsum()
    return pd.concat([pd.Series([initial_balance], index=[closed[0].entry_time]), balance])


def summary(trades: Sequence[Trade], initial_balance: float = 10000.0) -> dict:
    closed = [t for t in trades if t.exit_time is not None]
    curve = equity_curve(closed, initial_balance)

    return {
        "total_trades": len(closed),
        "win_rate": round(win_rate(closed), 4),
        "profit_factor": round(profit_factor(closed), 4),
        "expectancy": round(expectancy(closed), 2),
        "net_pnl": round(sum(t.pnl for t in closed), 2),
        "net_pnl_pct": round(sum(t.pnl for t in closed) / initial_balance, 4),
        "sharpe": round(sharpe_ratio(curve), 4),
    }
