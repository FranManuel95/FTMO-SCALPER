from typing import Sequence

import numpy as np
import pandas as pd

from src.core.types import Trade


def monthly_returns(trades: Sequence[Trade], initial_balance: float = 10000.0) -> pd.Series:
    closed = [t for t in trades if t.exit_time is not None]
    if not closed:
        return pd.Series(dtype=float)
    df = pd.DataFrame([{"month": t.exit_time.strftime("%Y-%m"), "pnl": t.pnl} for t in closed])
    monthly_pnl = df.groupby("month")["pnl"].sum()
    return monthly_pnl / initial_balance


def pnl_stability(trades: Sequence[Trade]) -> float:
    """Coeficiente de variación del PnL mensual. Menor = más estable."""
    monthly = monthly_returns(trades)
    if monthly.empty or monthly.std() == 0:
        return 0.0
    return float(monthly.std() / abs(monthly.mean()))


def max_consecutive_losses(trades: Sequence[Trade]) -> int:
    closed = sorted([t for t in trades if t.exit_time is not None], key=lambda t: t.exit_time)
    max_streak = 0
    streak = 0
    for t in closed:
        if t.pnl < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def recovery_factor(equity_curve: pd.Series) -> float:
    from src.metrics.drawdown import max_drawdown
    net_gain = equity_curve.iloc[-1] - equity_curve.iloc[0]
    dd = abs(max_drawdown(equity_curve))
    return net_gain / (dd * equity_curve.iloc[0]) if dd > 0 else 0.0
