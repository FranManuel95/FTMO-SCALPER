"""
Página Strategies — comportamiento por estrategia individual.

Permite ver cuáles están funcionando, cuáles están en racha mala, el funnel
de señales (cuántas se generaron vs ejecutaron) y un drift detector que
compara los últimos 10 trades vs el histórico.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.lib import data, metrics, formatting as fmt


st.set_page_config(page_title="Strategies", page_icon="🎯", layout="wide")
st.title("🎯 Strategies")

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
INITIAL_BALANCE = float(os.environ.get("FTMO_INITIAL_BALANCE", 160_000))

with st.sidebar:
    db_path = st.text_input("Ruta SQLite", DB_PATH)
    initial_balance = st.number_input("Balance inicial (€)", value=INITIAL_BALANCE, step=1000.0)
    days_lookback = st.slider("Lookback (días)", 1, 90, 30)

since_unix = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_lookback)).timestamp()
closes = data.load_position_closes(db_path, since_unix=since_unix)
signals = data.load_signals(db_path, since_unix=since_unix)

if closes.empty:
    st.info("Aún no hay trades cerrados en el periodo seleccionado.")
    st.stop()


# ── Tabla maestra ──────────────────────────────────────────────────────────────

st.subheader("Resumen por estrategia")
stats = metrics.per_strategy_stats(closes)

if not stats.empty:
    display = stats.copy()
    display["win_rate"] = display["win_rate"].round(1).astype(str) + "%"
    display["profit_factor"] = display["profit_factor"].round(2)
    display["net_total"] = display["net_total"].round(2)
    display["expectancy"] = display["expectancy"].round(2)
    display["max_dd"] = display["max_dd"].round(2)
    display["avg_winner"] = display["avg_winner"].round(2)
    display["avg_loser"] = display["avg_loser"].round(2)
    display["total_commission"] = display["total_commission"].round(2)
    display.columns = ["Trades", "W", "L", "WR", "PF", "Net €", "Expectancy €",
                       "MaxDD €", "Avg W €", "Avg L €", "Comm €", "Último"]
    st.dataframe(display, use_container_width=True)


# ── Curva de equity por estrategia ─────────────────────────────────────────────

st.divider()
st.subheader("Curvas de equity por estrategia (cum net)")

curves = []
for strat, g in closes.groupby("strategy_id"):
    g_sorted = g.sort_values("close_time")
    g_sorted = g_sorted.assign(cum_net=g_sorted["net"].fillna(g_sorted["pnl"]).cumsum())
    g_sorted["strategy_id"] = strat
    curves.append(g_sorted[["close_time", "cum_net", "strategy_id"]])

if curves:
    all_curves = pd.concat(curves, ignore_index=True)
    fig = px.line(
        all_curves, x="close_time", y="cum_net", color="strategy_id",
        labels={"close_time": "", "cum_net": "Net acumulado (€)"},
        height=450,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title="")
    st.plotly_chart(fig, use_container_width=True)


# ── Funnel de señales ──────────────────────────────────────────────────────────

st.divider()
st.subheader("Funnel de señales por estrategia")

if signals.empty:
    st.info("Sin eventos de señal en el periodo")
else:
    funnel = metrics.signal_funnel(signals)
    if not funnel.empty:
        funnel = funnel.reset_index()
        funnel["execution_rate_str"] = funnel["execution_rate"].astype(str) + "%"
        col_l, col_r = st.columns([2, 1])
        with col_l:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Ejecutadas", x=funnel["strategy_id"], y=funnel["executed"],
                marker_color="#2ca02c",
                text=funnel["executed"], textposition="inside",
            ))
            fig.add_trace(go.Bar(
                name="Rechazadas", x=funnel["strategy_id"], y=funnel["rejected"],
                marker_color="#d62728",
                text=funnel["rejected"], textposition="inside",
            ))
            fig.update_layout(
                barmode="stack", height=400,
                margin=dict(l=10, r=10, t=10, b=10),
                yaxis_title="Nº de señales",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.markdown("**Tasa de ejecución**")
            st.dataframe(
                funnel[["strategy_id", "total", "executed", "execution_rate_str"]]
                .set_index("strategy_id"),
                use_container_width=True,
            )

    rej = metrics.rejection_reasons(signals)
    if not rej.empty:
        st.markdown("**Motivos de rechazo**")
        st.dataframe(rej, use_container_width=True, hide_index=True)


# ── Drift: últimos N vs histórico ──────────────────────────────────────────────

st.divider()
st.subheader("Drift detector — WR reciente vs histórico")
recent_n = st.slider("Tamaño ventana reciente", 3, 30, 10)
drift = metrics.recent_vs_historical_wr(closes, recent_n=recent_n)

if drift.empty:
    st.info("Insuficientes datos para drift detection")
else:
    drift_display = drift.copy()
    drift_display["wr_all"] = drift_display["wr_all"].astype(str) + "%"
    drift_display["wr_recent"] = drift_display["wr_recent"].astype(str) + "%"
    drift_display["delta"] = drift_display["delta"].apply(
        lambda d: f"{fmt.trend_arrow(d, 5)} {d:+.1f}pp"
    )
    drift_display.columns = ["WR histórico", "WR reciente", "Δ", "N total", "N reciente"]
    st.dataframe(drift_display, use_container_width=True)


# ── Trades recientes por estrategia (sparkline-ish) ───────────────────────────

st.divider()
st.subheader("Últimos trades por estrategia (W/L pattern)")

for strat, g in closes.groupby("strategy_id"):
    g_sorted = g.sort_values("close_time").tail(20)
    cols = st.columns([1, 4])
    with cols[0]:
        st.markdown(f"**{strat}**")
        wr_strat = (g_sorted["net"].fillna(g_sorted["pnl"]) > 0).mean() * 100
        st.caption(f"WR últ. {len(g_sorted)}: {wr_strat:.0f}%")
    with cols[1]:
        nets = g_sorted["net"].fillna(g_sorted["pnl"]).tolist()
        line = "".join("🟢" if n > 0 else "🔴" for n in nets)
        st.markdown(f"<div style='font-size: 1.5em; letter-spacing: 2px;'>{line}</div>",
                    unsafe_allow_html=True)
