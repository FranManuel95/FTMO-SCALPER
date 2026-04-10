# risk/guardian.py — Motor de riesgo FTMO
# ESTE ARCHIVO NO SE MODIFICA SIN REVISIÓN EXHAUSTIVA

import os
from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum

class TradingStatus(Enum):
    ALLOWED    = "ALLOWED"
    DAILY_LOSS = "DAILY_LOSS_EXCEEDED"
    MAX_LOSS   = "MAX_LOSS_EXCEEDED"
    NEWS_BLOCK = "NEWS_BLOCK_ACTIVE"
    WEEKEND    = "WEEKEND_BLOCK"
    MAX_TRADES = "MAX_DAILY_TRADES"
    PAUSED     = "MANUAL_PAUSE"
    XMAS_BLOCK = "XMAS_BLOCK"

class FTMORiskGuardian:
    DAILY_LOSS_LIMIT_PCT  = 0.045
    MAX_LOSS_LIMIT_PCT    = 0.095
    RISK_PER_TRADE_PCT    = 0.005
    MAX_TRADES_PER_DAY    = 6
    NEWS_BLOCK_MINUTES    = 30
    MIN_RR_RATIO          = 2.0

    def __init__(self, initial_balance: float):
        self.initial_balance    = initial_balance
        self.daily_start_equity = initial_balance
        self.highest_balance    = initial_balance
        self.trades_today       = 0
        self.paused             = False
        self._last_reset_day    = None

    def _reset_daily_if_needed(self, current_equity: float):
        today = datetime.utcnow().date()
        if self._last_reset_day != today:
            self.daily_start_equity = current_equity
            self.trades_today       = 0
            self._last_reset_day    = today

    def can_trade(self, current_equity: float,
                  news_active: bool = False) -> TradingStatus:
        self._reset_daily_if_needed(current_equity)

        if self.paused:
            return TradingStatus.PAUSED

        # Filtro navideño: 20 Dic - 3 Ene
        now = datetime.utcnow()
        is_xmas = (now.month == 12 and now.day >= 20) or \
                  (now.month == 1  and now.day <= 3)
        if is_xmas:
            return TradingStatus.XMAS_BLOCK

        if now.weekday() == 4 and now.hour >= 21:
            return TradingStatus.WEEKEND
        if now.weekday() in [5, 6]:
            return TradingStatus.WEEKEND

        if news_active:
            return TradingStatus.NEWS_BLOCK

        if self.trades_today >= self.MAX_TRADES_PER_DAY:
            return TradingStatus.MAX_TRADES

        daily_loss = (self.daily_start_equity - current_equity) / self.initial_balance
        if daily_loss >= self.DAILY_LOSS_LIMIT_PCT:
            return TradingStatus.DAILY_LOSS

        self.highest_balance = max(self.highest_balance, current_equity)
        total_dd = (self.highest_balance - current_equity) / self.initial_balance
        if total_dd >= self.MAX_LOSS_LIMIT_PCT:
            return TradingStatus.MAX_LOSS

        return TradingStatus.ALLOWED

    def calculate_lot_size(self, balance: float, sl_pips: float,
                           pip_value: float = 10.0) -> float:
        risk_amount = balance * self.RISK_PER_TRADE_PCT
        lot_size    = risk_amount / (sl_pips * pip_value)
        return round(min(lot_size, 10.0), 2)

    def register_trade(self):
        self.trades_today += 1

    def get_status_report(self, current_equity: float) -> dict:
        daily_loss_pct = (self.daily_start_equity - current_equity) / self.initial_balance * 100
        total_dd_pct   = (self.highest_balance - current_equity) / self.initial_balance * 100
        return {
            "equity":            current_equity,
            "daily_loss_pct":    round(daily_loss_pct, 2),
            "total_dd_pct":      round(total_dd_pct, 2),
            "trades_today":      self.trades_today,
            "daily_limit":       self.DAILY_LOSS_LIMIT_PCT * 100,
            "max_dd_limit":      self.MAX_LOSS_LIMIT_PCT * 100,
            "safe_daily_margin": round(self.DAILY_LOSS_LIMIT_PCT * 100 - daily_loss_pct, 2),
        }