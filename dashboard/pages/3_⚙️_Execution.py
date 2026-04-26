"""
Página Execution — calidad de ejecución del bot.

Slippage por símbolo, quick-stop rate, comportamiento del trail, latencias
del runner. Aquí es donde se detectan los problemas operativos.
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


st.set_page_config(page_title="Execution", page_icon="⚙️", layout="wide")
st.title("⚙️ Execution Quality")

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
with st.sidebar:
    db_path = st.text_input("Ruta SQLite", DB_PATH)
    days_lookback = st.slider("Lookback (días)", 1, 90, 30)

since_unix = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_lookback)).timestamp()

orders = data.load_orders(db_path, since_unix=since_unix)
closes = data.load_position_closes(db_path, since_unix=since_unix)
trail = data.load_trail_updates(db_path, since_unix=since_unix)
ticks = data.load_strategy_ticks(db_path, since_unix=since_unix)


# ── Slippage por símbolo ───────────────────────────────────────────────────────

st.subheader("📐 Slippage por símbolo")

if orders.empty or "slippage_pips" not in orders.columns:
    st.info("Sin órdenes ejecutadas con datos de slippage")
else:
    sl_stats = metrics.slippage_stats(orders)
    if not sl_stats.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(sl_stats, width="stretch")
        with c2:
            df_sl = orders.dropna(subset=["slippage_pips"])
            fig = px.box(
                df_sl, x="symbol", y="slippage_pips",
                color="symbol", points="all",
                height=400,
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                yaxis_title="Slippage (pips, + = adverso)",
                xaxis_title="",
            )
            st.plotly_chart(fig, width="stretch")


# ── Quick-stop rate ────────────────────────────────────────────────────────────

st.divider()
st.subheader("⚡ Quick-stop rate (trades cerrados rápidamente)")

threshold_min = st.slider("Umbral (minutos)", 1, 30, 5)
threshold_s = threshold_min * 60

qs = metrics.quick_stop_rate(closes, threshold_seconds=threshold_s)
if qs.empty:
    st.info("Sin trades cerrados aún")
else:
    qs_display = qs.copy()
    qs_display["quick_pct_str"] = qs_display["quick_pct"].astype(str) + "%"
    qs_display.columns = ["Total trades", "Quick stops", "% rápidos", "_str"]
    qs_display = qs_display[["Total trades", "Quick stops", "% rápidos"]]

    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(qs_display, width="stretch")
    with c2:
        fig = px.bar(
            qs.reset_index(), x="strategy_id", y="quick_pct",
            color="quick_pct", color_continuous_scale="Reds",
            labels={"quick_pct": f"% trades < {threshold_min}m", "strategy_id": ""},
            height=400,
        )
        fig.add_hline(y=50, line_dash="dash", line_color="orange",
                      annotation_text="50% (alerta)", annotation_position="right")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")


# ── Distribución de duración ───────────────────────────────────────────────────

st.divider()
st.subheader("⏱ Distribución de duración de trades")

if not closes.empty and "duration_seconds" in closes.columns:
    dur_df = closes.dropna(subset=["duration_seconds"]).copy()
    dur_df["duration_min"] = dur_df["duration_seconds"] / 60
    dur_df["outcome"] = dur_df["net"].apply(lambda n: "Ganadora" if n > 0 else "Perdedora")
    fig = px.histogram(
        dur_df, x="duration_min", color="outcome",
        nbins=40, barmode="overlay",
        labels={"duration_min": "Duración (minutos)", "count": "Nº trades"},
        height=400,
        color_discrete_map={"Ganadora": "#2ca02c", "Perdedora": "#d62728"},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")


# ── Comportamiento del trail ───────────────────────────────────────────────────

st.divider()
st.subheader("🪤 Comportamiento del trailing stop")

if trail.empty:
    st.info("Sin eventos de trail registrados aún")
else:
    total = len(trail)
    applied = int(trail.get("applied", pd.Series([False])).sum())
    skipped = total - applied
    skip_reasons = trail[~trail["applied"].fillna(False)]["skip_reason"].value_counts() if "skip_reason" in trail else pd.Series()

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Evaluaciones", f"{total:,}")
    with c2: st.metric("Aplicadas", f"{applied:,}", delta=f"{applied/max(total,1)*100:.1f}%")
    with c3: st.metric("Saltadas", f"{skipped:,}")

    if not skip_reasons.empty:
        st.markdown("**Motivos de skip más frecuentes**")
        skip_df = skip_reasons.rename_axis("Motivo").reset_index(name="Conteo")
        st.dataframe(skip_df, width="stretch", hide_index=True)


# ── Latencias del runner ───────────────────────────────────────────────────────

st.divider()
st.subheader("⏲ Latencias del bot (últimas 24h)")

if ticks.empty:
    st.info("Sin métricas de tick aún")
else:
    last_24h = ticks[ticks["ts"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=24)]
    if last_24h.empty:
        st.info("Sin métricas de tick en últimas 24h")
    else:
        c1, c2 = st.columns(2)
        with c1:
            fig = px.histogram(
                last_24h, x="fetch_ms", nbins=30,
                labels={"fetch_ms": "fetch_bars (ms)"},
                height=300, title="Tiempo de fetch de barras",
            )
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")
        with c2:
            fig = px.histogram(
                last_24h, x="generator_ms", nbins=30,
                labels={"generator_ms": "generator (ms)"},
                height=300, title="Tiempo de generador",
            )
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")

        # Errores recientes
        errors = last_24h[last_24h["error"].notna() & (last_24h["error"] != "")]
        if not errors.empty:
            st.markdown("**❌ Errores recientes en strategy_tick**")
            err_table = errors[["ts", "strategy_id", "error"]].sort_values("ts", ascending=False).head(20)
            st.dataframe(err_table, width="stretch", hide_index=True)
        else:
            st.success("Sin errores en últimas 24h")
