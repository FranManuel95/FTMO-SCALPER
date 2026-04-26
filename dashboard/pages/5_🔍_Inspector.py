"""
Página Inspector — análisis forense por trade individual.

Buscar por ticket → ver TODA la timeline del trade: orden de entrada,
todas las evaluaciones del trail (aplicadas y saltadas), el cierre con
MFE/MAE, y un gráfico con SL/TP/precio para visualizar qué pasó.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.lib import data, formatting as fmt


st.set_page_config(page_title="Inspector", page_icon="🔍", layout="wide")
st.title("🔍 Trade Inspector")

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
with st.sidebar:
    db_path = st.text_input("Ruta SQLite", DB_PATH)


# ── Selector de ticket ─────────────────────────────────────────────────────────

closes = data.load_position_closes(db_path)
orders = data.load_orders(db_path)

available_tickets: list[int] = []
if not closes.empty:
    available_tickets.extend(closes["ticket"].astype(int).tolist())
if not orders.empty:
    available_tickets.extend(
        orders.dropna(subset=["ticket"])["ticket"].astype(int).tolist()
    )
available_tickets = sorted(set(available_tickets), reverse=True)

if not available_tickets:
    st.info("Aún no hay trades registrados")
    st.stop()

ticket = st.selectbox("Ticket", available_tickets, format_func=lambda t: f"#{t}")

# Cargar todos los eventos de este ticket
all_events = data.load_events(db_path, limit=10_000)
trade_events = all_events[all_events["ticket"] == ticket].sort_values("ts_unix")

if trade_events.empty:
    st.warning(f"No hay eventos para el ticket {ticket}")
    st.stop()

# Encontrar order y close
order_event = trade_events[trade_events["event_type"] == "order"].iloc[-1] if (trade_events["event_type"] == "order").any() else None
close_event = trade_events[trade_events["event_type"] == "position_close"].iloc[-1] if (trade_events["event_type"] == "position_close").any() else None
trail_events = trade_events[trade_events["event_type"] == "trail_update"].copy()


# ── Cabecera ───────────────────────────────────────────────────────────────────

if order_event is not None:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Estrategia", order_event.get("strategy_id", "—"))
    with c2: st.metric("Par", order_event.get("symbol", "—"))
    with c3: st.metric("Side", order_event.get("side", "—"))
    with c4:
        vol = order_event.get("volume")
        st.metric("Lotes", f"{vol:.2f}" if pd.notna(vol) else "—")
    with c5:
        slip = order_event.get("slippage_pips")
        st.metric("Slippage", fmt.fmt_pips(slip) if pd.notna(slip) else "—")


# ── Resumen del cierre ─────────────────────────────────────────────────────────

if close_event is not None:
    st.divider()
    st.subheader("📋 Resumen del cierre")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Net €", fmt.fmt_eur(close_event.get("net"), sign=True))
    with c2: st.metric("Duración", fmt.fmt_duration(close_event.get("duration_seconds")))
    with c3: st.metric("Motivo", close_event.get("close_reason", "—"))
    with c4:
        mfe = close_event.get("mfe")
        st.metric("MFE", f"{mfe:+.5f}" if pd.notna(mfe) else "—",
                  help="Max Favorable Excursion: cuánto se movió a favor en el peak")
    with c5:
        mae = close_event.get("mae")
        st.metric("MAE", f"{mae:+.5f}" if pd.notna(mae) else "—",
                  help="Max Adverse Excursion: cuánto se movió en contra en el valley")


# ── Gráfico de evolución del SL ────────────────────────────────────────────────

st.divider()
st.subheader("📉 Evolución del trade")

if order_event is not None and not trail_events.empty:
    fig = go.Figure()
    entry_price = order_event.get("fill_price") or order_event.get("signal_entry")
    sl_orig = order_event.get("signal_sl")
    tp = order_event.get("signal_tp")

    # Líneas horizontales: entry, original SL, TP
    fig.add_hline(y=entry_price, line_color="blue", line_width=2,
                  annotation_text=f"Entry {entry_price:.5f}", annotation_position="left")
    fig.add_hline(y=sl_orig, line_color="red", line_width=1, line_dash="dash",
                  annotation_text=f"SL inicial {sl_orig:.5f}", annotation_position="left")
    fig.add_hline(y=tp, line_color="green", line_width=1, line_dash="dash",
                  annotation_text=f"TP {tp:.5f}", annotation_position="left")

    # Trail SL aplicados (línea azul claro punteada)
    applied_trails = trail_events[trail_events["applied"].fillna(False)]
    if not applied_trails.empty:
        fig.add_trace(go.Scatter(
            x=applied_trails["ts"], y=applied_trails["computed_sl"],
            mode="lines+markers",
            name="Trail SL aplicado",
            line=dict(color="orange", width=2, shape="hv"),
            marker=dict(size=6, color="orange"),
        ))

    # High/low desde entrada (envolvente del precio observado)
    fig.add_trace(go.Scatter(
        x=trail_events["ts"], y=trail_events["highest_since_entry"],
        mode="lines", name="High since entry",
        line=dict(color="lightgreen", width=1, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=trail_events["ts"], y=trail_events["lowest_since_entry"],
        mode="lines", name="Low since entry",
        line=dict(color="lightcoral", width=1, dash="dot"),
    ))

    # Marca de cierre
    if close_event is not None:
        exit_price = close_event.get("exit_price")
        ts_close = pd.to_datetime(close_event.get("close_time"))
        fig.add_trace(go.Scatter(
            x=[ts_close], y=[exit_price],
            mode="markers+text",
            marker=dict(size=14, color="black", symbol="x"),
            text=["CIERRE"], textposition="top center",
            name="Cierre",
        ))

    fig.update_layout(
        height=500,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Precio",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.info("Sin eventos de trail registrados para este trade")


# ── Timeline completa ──────────────────────────────────────────────────────────

st.divider()
st.subheader("📜 Timeline cronológica")

icon_map = {
    "order": "🟦",
    "trail_update": "🪤",
    "position_close": "🏁",
    "signal": "📡",
    "system_event": "⚙️",
}

for _, evt in trade_events.iterrows():
    icon = icon_map.get(evt["event_type"], "•")
    ts = evt["ts"].strftime("%Y-%m-%d %H:%M:%S UTC")
    payload_summary = []
    for k in ["fill_price", "signal_sl", "signal_tp", "computed_sl", "applied",
              "skip_reason", "exit_price", "close_reason", "net", "slippage_pips"]:
        if k in evt and pd.notna(evt[k]) and evt[k] != "":
            payload_summary.append(f"{k}={evt[k]}")
    summary = " · ".join(payload_summary[:6])
    with st.expander(f"{icon} **{evt['event_type']}** — {ts}"):
        st.caption(summary)
        # Mostrar payload completo
        cols_show = [c for c in evt.index if c not in ("event_id", "ts", "ts_unix", "payload")]
        st.json({c: (str(evt[c]) if pd.notna(evt[c]) else None) for c in cols_show})
