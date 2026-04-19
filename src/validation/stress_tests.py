from copy import deepcopy
from typing import Sequence

from src.core.types import Trade
from src.metrics.performance import summary


def stress_spread(
    trades: Sequence[Trade],
    extra_cost_per_trade: float,
    initial_balance: float = 10000.0,
) -> dict:
    """Añade un coste adicional por trade y recalcula métricas."""
    stressed = deepcopy(list(trades))
    for t in stressed:
        if t.exit_time is not None:
            t.pnl -= extra_cost_per_trade

    return summary(stressed, initial_balance)


def stress_slippage(
    trades: Sequence[Trade],
    slippage_per_trade: float,
    initial_balance: float = 10000.0,
) -> dict:
    stressed = deepcopy(list(trades))
    for t in stressed:
        if t.exit_time is not None:
            t.pnl -= abs(slippage_per_trade)

    return summary(stressed, initial_balance)


def run_stress_suite(
    trades: Sequence[Trade],
    spread_costs: list[float],
    initial_balance: float = 10000.0,
) -> list[dict]:
    results = []
    for cost in spread_costs:
        result = stress_spread(trades, cost, initial_balance)
        result["extra_cost_per_trade"] = cost
        results.append(result)
    return results
