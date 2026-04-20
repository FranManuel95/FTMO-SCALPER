"""
StrategyState — tracking de señales ya ejecutadas para evitar duplicados.

En live, cada cierre de barra ejecuta los signal generators sobre la ventana
más reciente de barras. Una misma señal puede aparecer N veces si el generator
la emite en barras sucesivas (ej: breakout que persiste sobre el rango).

StrategyState usa una clave (strategy_id, symbol, timestamp) como huella
única para descartar repetidos y respetar max_signals_per_day.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta


class StrategyState:
    def __init__(self, retention_hours: int = 48):
        self.retention = timedelta(hours=retention_hours)
        self._fingerprints: set[tuple] = set()
        self._daily_count: dict[tuple[str, date], int] = defaultdict(int)

    def was_seen(self, strategy_id: str, symbol: str, ts: datetime) -> bool:
        return (strategy_id, symbol, ts) in self._fingerprints

    def mark_seen(self, strategy_id: str, symbol: str, ts: datetime) -> None:
        self._fingerprints.add((strategy_id, symbol, ts))
        self._daily_count[(strategy_id, ts.date())] += 1

    def daily_count(self, strategy_id: str, day: date) -> int:
        return self._daily_count[(strategy_id, day)]

    def prune(self, now: datetime) -> None:
        cutoff = now - self.retention
        self._fingerprints = {f for f in self._fingerprints if f[2] >= cutoff}
        active_days = {now.date(), (now - timedelta(days=1)).date()}
        for k in list(self._daily_count):
            if k[1] not in active_days:
                del self._daily_count[k]
