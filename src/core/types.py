from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class SignalType(str, Enum):
    BREAKOUT = "breakout"
    PULLBACK = "pullback"
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"


@dataclass
class Signal:
    symbol: str
    side: Side
    signal_type: SignalType
    timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0.0


@dataclass
class Trade:
    symbol: str
    side: Side
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN
    pnl: float = 0.0
    pnl_pct: float = 0.0
    tags: list[str] = field(default_factory=list)

    def close(self, exit_time: datetime, exit_price: float) -> None:
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.status = TradeStatus.CLOSED
        direction = 1 if self.side == Side.LONG else -1
        self.pnl = direction * (exit_price - self.entry_price) * self.size
        self.pnl_pct = direction * (exit_price - self.entry_price) / self.entry_price
