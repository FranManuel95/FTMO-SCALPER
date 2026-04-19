from datetime import date, datetime
from collections import defaultdict


class DailyLossGuard:
    """
    Bloquea nuevas operaciones si se alcanza el límite de pérdida diaria.
    Crítico para no fallar el challenge FTMO.
    """

    def __init__(self, initial_balance: float, max_daily_loss_pct: float = 0.05):
        self.initial_balance = initial_balance
        self.max_daily_loss = initial_balance * max_daily_loss_pct
        self._daily_pnl: dict[date, float] = defaultdict(float)
        self._blocked_days: set[date] = set()

    def record_pnl(self, pnl: float, timestamp: datetime) -> None:
        day = timestamp.date()
        self._daily_pnl[day] += pnl
        if self._daily_pnl[day] <= -self.max_daily_loss:
            self._blocked_days.add(day)

    def is_blocked(self, timestamp: datetime) -> bool:
        return timestamp.date() in self._blocked_days

    def daily_pnl(self, day: date) -> float:
        return self._daily_pnl.get(day, 0.0)

    def reset(self) -> None:
        self._daily_pnl.clear()
        self._blocked_days.clear()
