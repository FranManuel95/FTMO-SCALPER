from datetime import datetime, timezone

import pytest

from src.core.types import Side, Trade, TradeStatus
from src.metrics.performance import profit_factor, win_rate, expectancy, summary
from src.metrics.drawdown import max_drawdown
from src.metrics.ftmo_checks import check_daily_loss, check_max_loss, run_all_checks


def make_trade(pnl: float, entry_dt: datetime = None, exit_dt: datetime = None) -> Trade:
    if entry_dt is None:
        entry_dt = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    if exit_dt is None:
        exit_dt = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
    t = Trade(
        symbol="EURUSD",
        side=Side.LONG,
        entry_time=entry_dt,
        entry_price=1.1000,
        stop_loss=1.0990,
        take_profit=1.1020,
        size=1.0,
        exit_time=exit_dt,
        exit_price=1.1020 if pnl > 0 else 1.0990,
        status=TradeStatus.CLOSED,
        pnl=pnl,
    )
    return t


class TestProfitFactor:
    def test_basic(self):
        trades = [make_trade(100), make_trade(100), make_trade(-50)]
        assert profit_factor(trades) == pytest.approx(4.0)

    def test_no_losses(self):
        trades = [make_trade(100), make_trade(50)]
        assert profit_factor(trades) == float("inf")

    def test_empty(self):
        assert profit_factor([]) == float("inf")


class TestWinRate:
    def test_basic(self):
        trades = [make_trade(100), make_trade(100), make_trade(-50)]
        assert win_rate(trades) == pytest.approx(2 / 3)

    def test_empty(self):
        assert win_rate([]) == 0.0


class TestMaxDrawdown:
    def test_basic(self):
        import pandas as pd
        equity = pd.Series([10000, 10500, 9800, 10200])
        dd = max_drawdown(equity)
        assert dd == pytest.approx(-0.0667, abs=0.001)

    def test_no_drawdown(self):
        import pandas as pd
        equity = pd.Series([10000, 10100, 10200, 10300])
        assert max_drawdown(equity) == 0.0


class TestFtmoChecks:
    def test_daily_loss_no_violation(self):
        trades = [make_trade(100), make_trade(-200)]
        result = check_daily_loss(trades, initial_balance=10000)
        assert result["passed"] is True

    def test_daily_loss_violation(self):
        trades = [make_trade(-600)]
        result = check_daily_loss(trades, initial_balance=10000)
        assert result["passed"] is False
        assert result["violations"] == 1

    def test_max_loss_no_violation(self):
        trades = [make_trade(-900)]
        result = check_max_loss(trades, initial_balance=10000)
        assert result["passed"] is True

    def test_max_loss_violation(self):
        trades = [make_trade(-1100)]
        result = check_max_loss(trades, initial_balance=10000)
        assert result["passed"] is False
