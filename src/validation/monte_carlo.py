from typing import Sequence

import numpy as np
import pandas as pd

from src.core.types import Trade
from src.metrics.drawdown import max_drawdown


def monte_carlo_drawdown(
    trades: Sequence[Trade],
    initial_balance: float = 10000.0,
    n_simulations: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Shufflea los trades N veces y calcula la distribución de drawdowns máximos.
    """
    rng = np.random.default_rng(seed)
    pnls = np.array([t.pnl for t in trades if t.exit_time is not None])

    if len(pnls) == 0:
        return {"error": "No hay trades cerrados"}

    drawdowns = []
    for _ in range(n_simulations):
        shuffled = rng.permutation(pnls)
        equity = pd.Series(initial_balance + np.cumsum(shuffled))
        drawdowns.append(abs(max_drawdown(equity)))

    dd_array = np.array(drawdowns)

    return {
        "n_simulations": n_simulations,
        "mean_max_dd": round(float(np.mean(dd_array)), 4),
        "median_max_dd": round(float(np.median(dd_array)), 4),
        "p95_max_dd": round(float(np.percentile(dd_array, 95)), 4),
        "p99_max_dd": round(float(np.percentile(dd_array, 99)), 4),
        "prob_exceed_10pct": round(float((dd_array > 0.10).mean()), 4),
        "prob_exceed_5pct": round(float((dd_array > 0.05).mean()), 4),
    }
