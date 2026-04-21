from datetime import datetime, timezone

import pytest

from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.max_loss_guard import MaxLossGuard
from src.risk.position_sizing import size_by_fixed_risk, size_by_kelly


class TestDailyLossGuard:
    def test_not_blocked_initially(self):
        guard = DailyLossGuard(10000, max_daily_loss_pct=0.05)
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert guard.is_blocked(ts) is False

    def test_blocked_after_limit(self):
        guard = DailyLossGuard(10000, max_daily_loss_pct=0.05)
        ts = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        guard.record_pnl(-500.0, ts)
        assert guard.is_blocked(ts) is True

    def test_not_blocked_next_day(self):
        guard = DailyLossGuard(10000, max_daily_loss_pct=0.05)
        ts1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc)
        guard.record_pnl(-500.0, ts1)
        assert guard.is_blocked(ts2) is False


class TestMaxLossGuard:
    def test_not_triggered_initially(self):
        guard = MaxLossGuard(10000, max_loss_pct=0.10)
        assert guard.is_triggered() is False

    def test_triggered_after_limit(self):
        guard = MaxLossGuard(10000, max_loss_pct=0.10)
        guard.update(-1001.0)
        assert guard.is_triggered() is True

    def test_not_triggered_below_limit(self):
        guard = MaxLossGuard(10000, max_loss_pct=0.10)
        guard.update(-999.0)
        assert guard.is_triggered() is False


class TestPositionSizing:
    def test_basic_sizing(self):
        size = size_by_fixed_risk(
            account_balance=10000,
            risk_pct=0.01,
            entry_price=1.1000,
            stop_loss_price=1.0990,
        )
        # risk_amount=100, stop_distance=0.001 → 100/0.001 = 100,000 price units
        assert size == pytest.approx(100_000.0)

    def test_zero_stop_distance(self):
        size = size_by_fixed_risk(10000, 0.01, 1.1000, 1.1000)
        assert size == 0.0

    def test_kelly_positive(self):
        fraction = size_by_kelly(win_rate=0.55, avg_win=2.0, avg_loss=1.0)
        assert fraction > 0

    def test_kelly_negative_edge(self):
        fraction = size_by_kelly(win_rate=0.30, avg_win=1.0, avg_loss=1.0)
        assert fraction == 0.0
