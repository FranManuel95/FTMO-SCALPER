"""
Página Trades — histórico filtrable de operaciones.

Tabla con todos los trades cerrados, filtros por estrategia/símbolo/fecha,
resumen diario en tarjetas, y curva de PnL acumulado anotada.
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


st.set_page_config(page_title="Trades", page_icon="📜", layout="wide")
st.title("📜 Trade History")

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
INITIAL_BALANCE = float(os.environ.get("FTMO_INITIAL_BALANCE", 160_000))

with st.sidebar:
    db_path = st.text_input("Ruta SQLite", DB_PATH)
    initial_balance = st.number_input("Balance inicial (€)", value=INITIAL_BALANCE, step=1000.0)
    days_lookback = st.slider("Lookback (días)", 1, 365, 30)

since_unix = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_lookback)).timestamp()
closes = data.load_position_closes(db_path, since_unix=since_unix)

if closes.empty:
    st.info("Sin trades cerrados en el periodo")
    st.stop()

# ── Filtros ────────────────────────────────────────────────────────────────────

f1, f2, f3, f4 = st.columns(4)
with f1:
    sel_strats = st.multiselect("Estrategia", sorted(closes["strategy_id"].unique()))
with f2:
    sel_syms = st.multiselect("Símbolo", sorted(closes["symbol"].unique()))
with f3:
    sel_outcomes = st.multiselect("Outcome", ["Ganadora", "Perdedora"])
with f4:
    sel_reasons = st.multiselect("Motivo cierre", sorted(closes["close_reason"].dropna().unique()))

filtered = closes.copy()
if sel_strats:
    filtered = filtered[filtered["strategy_id"].isin(sel_strats)]
if sel_syms:
    filtered = filtered[filtered["symbol"].isin(sel_syms)]
if sel_outcomes:
    if "Ganadora" in sel_outcomes and "Perdedora" not in sel_outcomes:
        filtered = filtered[filtered["net"] > 0]
    elif "Perdedora" in sel_outcomes and "Ganadora" not in sel_outcomes:
        filtered = filtered[filtered["net"] <= 0]
if sel_reasons:
    filtered = filtered[filtered["close_reason"].isin(sel_reasons)]


# ── KPIs filtrados ─────────────────────────────────────────────────────────────

st.subheader("Resumen filtrado")
summary = metrics.trade_summary(filtered)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Trades", summary["n_trades"])
c2.metric("Win Rate", fmt.fmt_pct(summary["win_rate"]))
c3.metric("Profit Factor", f"{summary['profit_factor']:.2f}")
c4.metric("Net €", fmt.fmt_eur(summary["net_total"], sign=True))
c5.metric("Expectancy €", fmt.fmt_eur(summary["expectancy"], sign=True))


# ── Resumen diario ─────────────────────────────────────────────────────────────

st.divider()
st.subheader("Resumen diario")

if not filtered.empty:
    daily = filtered.assign(day=filtered["close_time"].dt.date).groupby("day").agg(
        trades=("ticket", "count"),
        winners=("net", lambda s: (s > 0).sum()),
        net=("net", "sum"),
    ).reset_index()
    daily["losers"] = daily["trades"] - daily["winners"]
    daily["wr"] = (daily["winners"] / daily["trades"] * 100).round(1)
    daily["color"] = daily["net"].apply(lambda x: "#2ca02c" if x >= 0 else "#d62728")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["day"], y=daily["net"],
        marker_color=daily["color"],
        text=daily.apply(lambda r: f"{r['winners']}W/{r['losers']}L<br>€{r['net']:+.0f}", axis=1),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Net: €%{y:+,.2f}<extra></extra>",
    ))
    fig.update_layout(
        height=350,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Net diario (€)",
        showlegend=False,
    )
    fig.add_hline(y=0, line_color="black", line_width=1)
    st.plotly_chart(fig, use_container_width=True)


# ── Curva de equity ────────────────────────────────────────────────────────────

st.divider()
st.subheader("Curva de equity (filtrada)")

eq = metrics.equity_curve(filtered, starting_balance=initial_balance)
if not eq.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq["close_time"], y=eq["equity"],
        mode="lines+markers",
        line=dict(color="#1f77b4", width=2),
        marker=dict(
            size=6,
            color=eq["net"].apply(lambda n: "#2ca02c" if n > 0 else "#d62728"),
        ),
        hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>" +
                      "Equity: €%{y:,.2f}<br>" +
                      "Trade: %{customdata[0]} %{customdata[1]}<br>" +
                      "Net: €%{customdata[2]:+,.2f}<extra></extra>",
        customdata=eq[["strategy_id", "symbol", "net"]].values,
    ))
    fig.add_hline(y=initial_balance, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Equity (€)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tabla detallada ────────────────────────────────────────────────────────────

st.divider()
st.subheader(f"Trades ({len(filtered)})")

display = filtered.sort_values("close_time", ascending=False).copy()
display["dur"] = display["duration_seconds"].apply(fmt.fmt_duration)
display["open_time_str"] = display["open_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
display["mfe_pct"] = (display["mfe"] / display["entry_price"].abs() * 100).round(3)
display["mae_pct"] = (display["mae"] / display["entry_price"].abs() * 100).round(3)

cols_display = [
    "open_time_str", "strategy_id", "symbol", "side", "ticket",
    "entry_price", "exit_price", "original_sl", "final_sl", "take_profit",
    "volume", "dur", "close_reason",
    "mfe_pct", "mae_pct",
    "pnl", "commission", "swap", "net",
]
cols_display = [c for c in cols_display if c in display.columns]
display = display[cols_display]
display.columns = [
    "Open", "Estrategia", "Par", "Side", "Ticket",
    "Entry", "Exit", "Orig SL", "Final SL", "TP",
    "Lots", "Dur", "Cierre",
    "MFE %", "MAE %",
    "PnL €", "Comm €", "Swap €", "Net €",
][:len(cols_display)]
st.dataframe(display, use_container_width=True, hide_index=True, height=400)

# CSV export
csv = filtered.to_csv(index=False)
st.download_button("⬇ Descargar CSV", csv, file_name=f"trades_{days_lookback}d.csv", mime="text/csv")
