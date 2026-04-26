"""
EventLogger — sistema de observabilidad estructurada para el bot live.

Cada evento se escribe a dos sitios:
  1. JSONL (append-only, durable, una línea por evento) — fuente de la verdad
  2. SQLite (queryable, indexada) — derivada del JSONL, regenerable

Los 8 tipos de eventos cubren el ciclo completo de vida de cada trade:

  - strategy_tick    : ejecución periódica de una estrategia (latencias, n señales)
  - signal           : señal generada (con was_executed y filter_reason)
  - guard_check      : un guard (daily/max loss) bloqueó o aprobó
  - order            : orden enviada a MT5 (con slippage real medido)
  - trail_update     : evaluación del trail (aplicado o saltado, motivo)
  - position_close   : posición cerrada (con MFE/MAE y close_reason inferido)
  - system_event     : eventos del bot (start/stop/disconnect/recovery/exception)
  - market_snapshot  : snapshot periódico de cuenta (cada minuto)

El logger es thread-safe (lock interno) y degrada con elegancia: si SQLite falla,
sigue escribiendo a JSONL. Si JSONL falla, sigue funcionando el bot.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Tipos de evento — usar constantes para evitar typos
class EventType:
    STRATEGY_TICK = "strategy_tick"
    SIGNAL = "signal"
    GUARD_CHECK = "guard_check"
    ORDER = "order"
    TRAIL_UPDATE = "trail_update"
    POSITION_CLOSE = "position_close"
    SYSTEM_EVENT = "system_event"
    MARKET_SNAPSHOT = "market_snapshot"


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,
    ts           TEXT NOT NULL,         -- ISO 8601 UTC
    ts_unix      REAL NOT NULL,         -- Unix timestamp (sortable, indexable)
    event_type   TEXT NOT NULL,
    strategy_id  TEXT,
    symbol       TEXT,
    ticket       INTEGER,
    payload      TEXT NOT NULL          -- JSON con todos los campos específicos del evento
);

CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts_unix);
CREATE INDEX IF NOT EXISTS idx_events_type      ON events(event_type, ts_unix);
CREATE INDEX IF NOT EXISTS idx_events_strategy  ON events(strategy_id, ts_unix);
CREATE INDEX IF NOT EXISTS idx_events_ticket    ON events(ticket, ts_unix);
CREATE INDEX IF NOT EXISTS idx_events_symbol    ON events(symbol, ts_unix);
"""


class EventLogger:
    """Logger estructurado dual (JSONL + SQLite) thread-safe."""

    def __init__(self, db_path: str | Path, jsonl_path: str | Path):
        self.db_path = Path(db_path)
        self.jsonl_path = Path(jsonl_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # check_same_thread=False — el lock garantiza serialización
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

        self._jsonl_fp = open(self.jsonl_path, "a", buffering=1)  # line-buffered
        logger.info(
            f"EventLogger inicializado | sqlite={self.db_path} | jsonl={self.jsonl_path}"
        )

    # ── API pública ────────────────────────────────────────────────────────────

    def emit(
        self,
        event_type: str,
        *,
        strategy_id: str | None = None,
        symbol: str | None = None,
        ticket: int | None = None,
        **payload: Any,
    ) -> str:
        """Emite un evento. Devuelve el event_id."""
        event_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        ts_iso = now.isoformat()
        ts_unix = now.timestamp()

        record = {
            "event_id": event_id,
            "ts": ts_iso,
            "ts_unix": ts_unix,
            "event_type": event_type,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "ticket": ticket,
            "payload": payload,
        }

        with self._lock:
            self._write_jsonl(record)
            self._write_sqlite(record)

        return event_id

    def query(
        self,
        event_type: str | None = None,
        strategy_id: str | None = None,
        ticket: int | None = None,
        symbol: str | None = None,
        since_unix: float | None = None,
        until_unix: float | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Lectura sencilla para tests o scripts. Para el dashboard usar pandas + read_sql."""
        query = "SELECT event_id, ts, ts_unix, event_type, strategy_id, symbol, ticket, payload FROM events WHERE 1=1"
        params: list[Any] = []
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        if ticket is not None:
            query += " AND ticket = ?"
            params.append(ticket)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if since_unix is not None:
            query += " AND ts_unix >= ?"
            params.append(since_unix)
        if until_unix is not None:
            query += " AND ts_unix <= ?"
            params.append(until_unix)
        query += " ORDER BY ts_unix DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            cur = self._conn.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "event_id": r[0],
                "ts": r[1],
                "ts_unix": r[2],
                "event_type": r[3],
                "strategy_id": r[4],
                "symbol": r[5],
                "ticket": r[6],
                "payload": json.loads(r[7]),
            }
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._jsonl_fp.close()
            except Exception:  # noqa: BLE001
                pass

    # ── Helpers tipados para cada evento ───────────────────────────────────────
    # Estos métodos son syntactic sugar — todos llaman a emit() con el event_type correcto.
    # Tienen los argumentos esperados explícitos para que el IDE ayude en el wire-up.

    def strategy_tick(
        self,
        strategy_id: str,
        symbol: str,
        n_bars: int,
        last_bar_ts: str | None,
        n_signals: int,
        n_filtered: int,
        n_executed: int,
        fetch_ms: float,
        generator_ms: float,
        error: str | None = None,
    ) -> str:
        return self.emit(
            EventType.STRATEGY_TICK,
            strategy_id=strategy_id,
            symbol=symbol,
            n_bars=n_bars,
            last_bar_ts=last_bar_ts,
            n_signals=n_signals,
            n_filtered=n_filtered,
            n_executed=n_executed,
            fetch_ms=round(fetch_ms, 2),
            generator_ms=round(generator_ms, 2),
            error=error,
        )

    def signal(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        signal_ts: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        atr_at_signal: float,
        was_executed: bool,
        filter_reason: str | None = None,
    ) -> str:
        return self.emit(
            EventType.SIGNAL,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            signal_ts=signal_ts,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr_at_signal=atr_at_signal,
            was_executed=was_executed,
            filter_reason=filter_reason,
        )

    def guard_check(
        self,
        guard_name: str,
        strategy_id: str | None,
        triggered: bool,
        reason: str,
        daily_pnl: float | None = None,
        equity: float | None = None,
        threshold: float | None = None,
    ) -> str:
        return self.emit(
            EventType.GUARD_CHECK,
            strategy_id=strategy_id,
            guard_name=guard_name,
            triggered=triggered,
            reason=reason,
            daily_pnl=daily_pnl,
            equity=equity,
            threshold=threshold,
        )

    def order(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        ticket: int | None,
        signal_entry: float,
        signal_sl: float,
        signal_tp: float,
        fill_price: float | None,
        volume: float,
        intended_volume: float,
        slippage_pips: float | None,
        retcode: int | None,
        comment: str | None,
        bid_at_send: float | None = None,
        ask_at_send: float | None = None,
    ) -> str:
        return self.emit(
            EventType.ORDER,
            strategy_id=strategy_id,
            symbol=symbol,
            ticket=ticket,
            side=side,
            signal_entry=signal_entry,
            signal_sl=signal_sl,
            signal_tp=signal_tp,
            fill_price=fill_price,
            volume=volume,
            intended_volume=intended_volume,
            slippage_pips=slippage_pips,
            retcode=retcode,
            comment=comment,
            bid_at_send=bid_at_send,
            ask_at_send=ask_at_send,
        )

    def trail_update(
        self,
        strategy_id: str,
        symbol: str,
        ticket: int,
        side: str,
        current_sl: float,
        computed_sl: float | None,
        applied: bool,
        skip_reason: str | None,
        highest_since_entry: float,
        lowest_since_entry: float,
        atr_at_signal: float,
        trail_mult: float,
    ) -> str:
        return self.emit(
            EventType.TRAIL_UPDATE,
            strategy_id=strategy_id,
            symbol=symbol,
            ticket=ticket,
            side=side,
            current_sl=current_sl,
            computed_sl=computed_sl,
            applied=applied,
            skip_reason=skip_reason,
            highest_since_entry=highest_since_entry,
            lowest_since_entry=lowest_since_entry,
            atr_at_signal=atr_at_signal,
            trail_mult=trail_mult,
        )

    def position_close(
        self,
        strategy_id: str,
        symbol: str,
        ticket: int,
        side: str,
        open_time: str,
        close_time: str,
        duration_seconds: int,
        entry_price: float,
        exit_price: float,
        original_sl: float,
        final_sl: float,
        take_profit: float,
        volume: float,
        pnl: float,
        commission: float,
        swap: float,
        net: float,
        close_reason: str,
        mfe: float | None = None,
        mae: float | None = None,
    ) -> str:
        return self.emit(
            EventType.POSITION_CLOSE,
            strategy_id=strategy_id,
            symbol=symbol,
            ticket=ticket,
            side=side,
            open_time=open_time,
            close_time=close_time,
            duration_seconds=duration_seconds,
            entry_price=entry_price,
            exit_price=exit_price,
            original_sl=original_sl,
            final_sl=final_sl,
            take_profit=take_profit,
            volume=volume,
            pnl=pnl,
            commission=commission,
            swap=swap,
            net=net,
            close_reason=close_reason,
            mfe=mfe,
            mae=mae,
        )

    def system_event(self, event_name: str, **details: Any) -> str:
        return self.emit(EventType.SYSTEM_EVENT, event_name=event_name, **details)

    def market_snapshot(
        self,
        equity: float,
        balance: float,
        free_margin: float,
        margin: float,
        n_open_positions: int,
        daily_pnl: float,
    ) -> str:
        return self.emit(
            EventType.MARKET_SNAPSHOT,
            equity=equity,
            balance=balance,
            free_margin=free_margin,
            margin=margin,
            n_open_positions=n_open_positions,
            daily_pnl=daily_pnl,
        )

    # ── Internos ───────────────────────────────────────────────────────────────

    def _write_jsonl(self, record: dict) -> None:
        try:
            self._jsonl_fp.write(json.dumps(record, default=str) + "\n")
            self._jsonl_fp.flush()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"EventLogger JSONL write fallo: {e}")

    def _write_sqlite(self, record: dict) -> None:
        try:
            self._conn.execute(
                "INSERT INTO events(event_id, ts, ts_unix, event_type, strategy_id, symbol, ticket, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["event_id"],
                    record["ts"],
                    record["ts_unix"],
                    record["event_type"],
                    record["strategy_id"],
                    record["symbol"],
                    record["ticket"],
                    json.dumps(record["payload"], default=str),
                ),
            )
            self._conn.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"EventLogger SQLite write fallo: {e}")


class NullEventLogger:
    """No-op logger — usado por defecto cuando no se quiere observabilidad (tests, dry-run sin DB)."""

    def emit(self, *args, **kwargs) -> str: return ""
    def query(self, *args, **kwargs) -> list[dict]: return []
    def close(self) -> None: pass
    def strategy_tick(self, *args, **kwargs) -> str: return ""
    def signal(self, *args, **kwargs) -> str: return ""
    def guard_check(self, *args, **kwargs) -> str: return ""
    def order(self, *args, **kwargs) -> str: return ""
    def trail_update(self, *args, **kwargs) -> str: return ""
    def position_close(self, *args, **kwargs) -> str: return ""
    def system_event(self, *args, **kwargs) -> str: return ""
    def market_snapshot(self, *args, **kwargs) -> str: return ""
