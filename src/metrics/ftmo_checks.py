from datetime import date
from collections import defaultdict
from typing import Sequence

import pandas as pd

from src.core.types import Trade

MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_LOSS_PCT = 0.10
MIN_PROFIT_FACTOR = 1.3
MIN_TRADING_DAYS = 4


def check_daily_loss(
    trades: Sequence[Trade],
    initial_balance: float,
    max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT,
) -> dict:
    """Detecta qué días se hubiera violado el límite de pérdida diaria."""
    daily_pnl: dict[date, float] = defaultdict(float)
    for t in trades:
        if t.exit_time is not None:
            daily_pnl[t.exit_time.date()] += t.pnl

    limit = initial_balance * max_daily_loss_pct
    violations = {day: pnl for day, pnl in daily_pnl.items() if pnl <= -limit}

    return {
        "violations": len(violations),
        "violation_days": sorted(violations.keys()),
        "worst_day_pnl": min(daily_pnl.values()) if daily_pnl else 0.0,
        "passed": len(violations) == 0,
    }


def check_max_loss(
    trades: Sequence[Trade],
    initial_balance: float,
    max_total_loss_pct: float = MAX_TOTAL_LOSS_PCT,
) -> dict:
    """Verifica que el drawdown total nunca superó el límite máximo."""
    balance = initial_balance
    min_balance = initial_balance
    limit = initial_balance * (1 - max_total_loss_pct)
    violated = False

    for t in sorted(trades, key=lambda x: x.exit_time or x.entry_time):
        if t.exit_time is not None:
            balance += t.pnl
            min_balance = min(min_balance, balance)
            if balance <= limit:
                violated = True

    return {
        "violated": violated,
        "min_balance": round(min_balance, 2),
        "max_drawdown_pct": round((initial_balance - min_balance) / initial_balance, 4),
        "passed": not violated,
    }


def check_consistency(
    trades: Sequence[Trade],
    initial_balance: float,
) -> dict:
    """Evalúa consistencia mensual básica."""
    closed = [t for t in trades if t.exit_time is not None]
    if not closed:
        return {"passed": False, "monthly_pnl": {}}

    df = pd.DataFrame([{"month": t.exit_time.strftime("%Y-%m"), "pnl": t.pnl} for t in closed])
    monthly = df.groupby("month")["pnl"].sum()
    profitable_months = (monthly > 0).sum()

    return {
        "months_traded": len(monthly),
        "profitable_months": int(profitable_months),
        "monthly_pnl": monthly.to_dict(),
        "passed": bool(profitable_months >= len(monthly) * 0.6),
    }


def run_all_checks(
    trades: Sequence[Trade],
    initial_balance: float = 10000.0,
) -> dict:
    daily = check_daily_loss(trades, initial_balance)
    total = check_max_loss(trades, initial_balance)
    consistency = check_consistency(trades, initial_balance)

    all_passed = daily["passed"] and total["passed"] and consistency["passed"]

    return {
        "overall": "PASS" if all_passed else "FAIL",
        "daily_loss_check": daily,
        "max_loss_check": total,
        "consistency_check": consistency,
    }
