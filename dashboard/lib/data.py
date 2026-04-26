"""
Capa de acceso a datos del dashboard.

Lee la base SQLite generada por EventLogger y devuelve DataFrames preparados
para visualización. Todas las funciones cachean con TTL para que el dashboard
sea responsive sin saturar el disco.

Convenciones:
  - Todas las funciones aceptan `db_path` (default: data/events.db)
  - Devuelven DataFrames con `ts` como columna datetime (UTC tz-aware)
  - Las columnas del payload se exponen al nivel superior (no anidadas)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


DEFAULT_DB = "data/events.db"
DEFAULT_TTL = 30  # segundos — refresh agresivo para "near real-time"


# ── Helpers de conexión ────────────────────────────────────────────────────────

def _connect(db_path: str | Path) -> sqlite3.Connection:
    """Conexión read-only para que el bot pueda escribir simultáneamente."""
    p = Path(db_path)
    if not p.exists():
        # Devolver conexión a DB vacía in-memory para no romper el dashboard
        # cuando el bot aún no ha generado eventos
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            "CREATE TABLE events (event_id TEXT, ts TEXT, ts_unix REAL, "
            "event_type TEXT, strategy_id TEXT, symbol TEXT, ticket INTEGER, payload TEXT);"
        )
        return conn
    uri = f"file:{p.resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _explode_payload(df: pd.DataFrame) -> pd.DataFrame:
    """Expande la columna payload (JSON string) a columnas individuales."""
    if df.empty:
        return df
    payload_df = pd.json_normalize(df["payload"].apply(json.loads))
    out = df.drop(columns=["payload"]).reset_index(drop=True)
    out = pd.concat([out, payload_df.reset_index(drop=True)], axis=1)
    return out


# ── Loaders por tipo de evento ─────────────────────────────────────────────────

@st.cache_data(ttl=DEFAULT_TTL, show_spinner=False)
def load_events(
    db_path: str = DEFAULT_DB,
    event_type: str | None = None,
    since_unix: float | None = None,
    until_unix: float | None = None,
    limit: int = 100_000,
) -> pd.DataFrame:
    """Carga eventos crudos de SQLite. Para uso general."""
    conn = _connect(db_path)
    q = "SELECT event_id, ts, ts_unix, event_type, strategy_id, symbol, ticket, payload FROM events WHERE 1=1"
    params: list = []
    if event_type:
        q += " AND event_type = ?"
        params.append(event_type)
    if since_unix is not None:
        q += " AND ts_unix >= ?"
        params.append(since_unix)
    if until_unix is not None:
        q += " AND ts_unix <= ?"
        params.append(until_unix)
    q += " ORDER BY ts_unix DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(q, conn, params=params)
    conn.close()
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return _explode_payload(df)


def load_position_closes(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    """Trades cerrados — la tabla más importante del dashboard."""
    df = load_events(db_path, event_type="position_close", since_unix=since_unix)
    if df.empty:
        return df
    # Tipos
    for col in ["entry_price", "exit_price", "original_sl", "final_sl", "take_profit",
                "volume", "pnl", "commission", "swap", "net", "mfe", "mae"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["duration_seconds"] = pd.to_numeric(df.get("duration_seconds"), errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
    df["close_time"] = pd.to_datetime(df["close_time"], utc=True, errors="coerce")
    return df.sort_values("close_time")


def load_orders(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    df = load_events(db_path, event_type="order", since_unix=since_unix)
    if df.empty:
        return df
    for col in ["signal_entry", "signal_sl", "signal_tp", "fill_price",
                "volume", "intended_volume", "slippage_pips",
                "bid_at_send", "ask_at_send"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_signals(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    df = load_events(db_path, event_type="signal", since_unix=since_unix)
    if df.empty:
        return df
    for col in ["entry_price", "stop_loss", "take_profit", "atr_at_signal"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_strategy_ticks(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    df = load_events(db_path, event_type="strategy_tick", since_unix=since_unix)
    if df.empty:
        return df
    for col in ["n_bars", "n_signals", "n_filtered", "n_executed",
                "fetch_ms", "generator_ms"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_trail_updates(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    df = load_events(db_path, event_type="trail_update", since_unix=since_unix)
    if df.empty:
        return df
    for col in ["current_sl", "computed_sl", "highest_since_entry",
                "lowest_since_entry", "atr_at_signal", "trail_mult"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_market_snapshots(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    df = load_events(db_path, event_type="market_snapshot", since_unix=since_unix)
    if df.empty:
        return df
    for col in ["equity", "balance", "free_margin", "margin", "daily_pnl"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["n_open_positions"] = pd.to_numeric(df.get("n_open_positions"), errors="coerce")
    return df


def load_system_events(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    return load_events(db_path, event_type="system_event", since_unix=since_unix)


def load_guard_checks(db_path: str = DEFAULT_DB, since_unix: float | None = None) -> pd.DataFrame:
    return load_events(db_path, event_type="guard_check", since_unix=since_unix)


def get_latest_snapshot(db_path: str = DEFAULT_DB) -> dict | None:
    """Snapshot más reciente — usado para el header del dashboard."""
    df = load_market_snapshots(db_path)
    if df.empty:
        return None
    return df.iloc[-1].to_dict()


def get_open_tickets(db_path: str = DEFAULT_DB) -> set[int]:
    """Tickets actualmente abiertos (orders sin position_close correspondiente)."""
    orders = load_orders(db_path)
    closes = load_position_closes(db_path)
    if orders.empty:
        return set()
    opened = {int(t) for t in orders.dropna(subset=["ticket"])["ticket"].unique() if t}
    closed = set(closes["ticket"].astype(int).unique()) if not closes.empty else set()
    return opened - closed


def get_db_health(db_path: str = DEFAULT_DB) -> dict:
    """Resumen rápido para diagnóstico."""
    p = Path(db_path)
    if not p.exists():
        return {"exists": False, "size_mb": 0, "n_events": 0, "last_event_ts": None}
    conn = _connect(db_path)
    cur = conn.execute("SELECT COUNT(*), MAX(ts_unix) FROM events")
    n, last_ts = cur.fetchone()
    conn.close()
    return {
        "exists": True,
        "size_mb": round(p.stat().st_size / 1_048_576, 2),
        "n_events": n or 0,
        "last_event_ts": pd.to_datetime(last_ts, unit="s", utc=True) if last_ts else None,
    }
