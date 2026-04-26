"""Tests del EventLogger y de los cálculos del dashboard."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.live.event_logger import EventLogger, EventType, NullEventLogger


# ── EventLogger core ───────────────────────────────────────────────────────────

@pytest.fixture
def logger(tmp_path: Path) -> EventLogger:
    db = tmp_path / "events.db"
    jsonl = tmp_path / "events.jsonl"
    el = EventLogger(db, jsonl)
    yield el
    el.close()


def test_emit_writes_to_both_jsonl_and_sqlite(logger: EventLogger, tmp_path: Path):
    eid = logger.emit(EventType.STRATEGY_TICK, strategy_id="x", n_signals=2)
    assert eid

    # JSONL
    lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "strategy_tick"
    assert record["strategy_id"] == "x"
    assert record["payload"]["n_signals"] == 2

    # SQLite
    rows = logger.query(event_type="strategy_tick")
    assert len(rows) == 1
    assert rows[0]["payload"]["n_signals"] == 2


def test_query_filters_by_strategy_and_ticket(logger: EventLogger):
    logger.emit(EventType.ORDER, strategy_id="a", ticket=100, fill_price=1.0)
    logger.emit(EventType.ORDER, strategy_id="b", ticket=200, fill_price=2.0)
    logger.emit(EventType.ORDER, strategy_id="a", ticket=101, fill_price=3.0)

    a_orders = logger.query(strategy_id="a")
    assert len(a_orders) == 2

    t100 = logger.query(ticket=100)
    assert len(t100) == 1
    assert t100[0]["payload"]["fill_price"] == 1.0


def test_typed_helpers_emit_correct_event_type(logger: EventLogger):
    logger.signal(
        strategy_id="x", symbol="EURUSD", side="LONG",
        signal_ts="2026-01-01T00:00:00", entry_price=1.1, stop_loss=1.09,
        take_profit=1.13, atr_at_signal=0.001, was_executed=True, filter_reason=None,
    )
    logger.position_close(
        strategy_id="x", symbol="EURUSD", ticket=42, side="LONG",
        open_time="2026-01-01T00:00:00", close_time="2026-01-01T01:00:00",
        duration_seconds=3600, entry_price=1.1, exit_price=1.13,
        original_sl=1.09, final_sl=1.10, take_profit=1.13,
        volume=1.0, pnl=300.0, commission=-5.0, swap=0.0, net=295.0,
        close_reason="take_profit", mfe=0.03, mae=-0.005,
    )
    types = {r["event_type"] for r in logger.query()}
    assert types == {"signal", "position_close"}


def test_close_logger_does_not_raise(logger: EventLogger):
    logger.close()
    # Idempotente
    logger.close()


# ── NullEventLogger ────────────────────────────────────────────────────────────

def test_null_logger_no_ops():
    null = NullEventLogger()
    # Todos los métodos deben existir y no lanzar
    null.emit("anything", foo="bar")
    null.signal(strategy_id="x", symbol="Y", side="LONG", signal_ts="t",
                entry_price=1, stop_loss=0, take_profit=2, atr_at_signal=0.1,
                was_executed=True, filter_reason=None)
    null.system_event("test")
    assert null.query() == []
    null.close()


# ── Métricas del dashboard ─────────────────────────────────────────────────────

def test_trade_summary_basics():
    from dashboard.lib.metrics import trade_summary

    closes = pd.DataFrame({
        "net": [100.0, -50.0, 200.0, -30.0],
        "pnl": [100.0, -50.0, 200.0, -30.0],
        "commission": [-2, -2, -2, -2],
    })
    s = trade_summary(closes)
    assert s["n_trades"] == 4
    assert s["n_winners"] == 2
    assert s["n_losers"] == 2
    assert s["win_rate"] == 50.0
    assert s["net_total"] == 220.0
    assert s["profit_factor"] == pytest.approx(300.0 / 80.0, rel=0.01)


def test_quick_stop_rate():
    from dashboard.lib.metrics import quick_stop_rate

    closes = pd.DataFrame({
        "ticket": [1, 2, 3, 4],
        "strategy_id": ["a", "a", "b", "b"],
        "duration_seconds": [60, 600, 30, 1800],
        "net": [-10, 50, -10, 100],
        "pnl": [-10, 50, -10, 100],
    })
    qs = quick_stop_rate(closes, threshold_seconds=300)
    assert qs.loc["a", "quick"] == 1
    assert qs.loc["a", "total"] == 2
    assert qs.loc["a", "quick_pct"] == 50.0
    assert qs.loc["b", "quick_pct"] == 50.0


def test_detect_anomalies_quick_stops():
    from dashboard.lib.metrics import detect_anomalies

    closes = pd.DataFrame({
        "ticket": list(range(5)),
        "strategy_id": ["fast"] * 5,
        "symbol": ["EURGBP"] * 5,
        "duration_seconds": [30, 60, 90, 120, 200],  # todos < 5 min
        "net": [-10, -20, -30, -10, -5],
        "pnl": [-10, -20, -30, -10, -5],
        "close_time": pd.to_datetime(["2026-01-01"] * 5, utc=True),
    })
    anomalies = detect_anomalies(closes, pd.DataFrame())
    cats = [a["category"] for a in anomalies]
    assert "quick_stops" in cats
    qs_anomaly = next(a for a in anomalies if a["category"] == "quick_stops")
    assert qs_anomaly["severity"] == "high"  # 100% quick stops


def test_per_strategy_stats():
    from dashboard.lib.metrics import per_strategy_stats

    closes = pd.DataFrame({
        "ticket": [1, 2, 3, 4],
        "strategy_id": ["a", "a", "b", "b"],
        "net": [100.0, -50.0, 200.0, -100.0],
        "pnl": [100.0, -50.0, 200.0, -100.0],
        "commission": [-2, -2, -2, -2],
        "close_time": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"], utc=True),
    })
    stats = per_strategy_stats(closes)
    assert "a" in stats.index
    assert "b" in stats.index
    assert stats.loc["a", "n_trades"] == 2
    assert stats.loc["a", "win_rate"] == 50.0


# ── Formatting ─────────────────────────────────────────────────────────────────

def test_format_helpers():
    from dashboard.lib.formatting import (
        fmt_eur, fmt_pct, fmt_pips, fmt_duration, severity_color,
    )
    assert fmt_eur(1234.5) == "€1,234.50"
    assert fmt_eur(-100, sign=True) == "€-100.00"
    assert fmt_pct(34.5) == "34.5%"
    assert fmt_pips(2.3) == "+2.3 pips"
    assert fmt_duration(45) == "45s"
    assert fmt_duration(125) == "2m 5s"
    assert fmt_duration(3661) == "1h 1m"
    assert fmt_duration(None) == "—"
    assert severity_color("high") == "🔴"
