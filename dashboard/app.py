"""
Dashboard principal — página Overview.

Muestra el estado actual del bot y la cuenta de un vistazo.
Ejecutar con:
  streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Hacer importables lib/ y src/ desde la ruta del proyecto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.lib import data, metrics, formatting as fmt


# ── Configuración ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FTMO Scalper Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
INITIAL_BALANCE = float(os.environ.get("FTMO_INITIAL_BALANCE", 160_000))
DAILY_LOSS_LIMIT_PCT = 5.0
MAX_LOSS_LIMIT_PCT = 10.0
PROFIT_TARGET_PCT = 10.0
HEARTBEAT_WARN_SECONDS = 120


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuración")
    db_path = st.text_input("Ruta SQLite", DB_PATH)
    initial_balance = st.number_input(
        "Balance inicial (€)",
        value=INITIAL_BALANCE, step=1000.0, format="%.2f",
    )
    refresh_seconds = st.slider("Auto-refresh (segundos)", 10, 120, 30)
    st.divider()
    health = data.get_db_health(db_path)
    if health["exists"]:
        st.metric("Eventos registrados", f"{health['n_events']:,}")
        st.caption(f"DB: {health['size_mb']} MB")
        if health["last_event_ts"] is not None:
            now = datetime.now(timezone.utc)
            age = (now - health["last_event_ts"]).total_seconds()
            color = "🟢" if age < HEARTBEAT_WARN_SECONDS else "🔴"
            st.caption(f"{color} Último evento hace {fmt.fmt_duration(age)}")
    else:
        st.warning(f"DB no encontrada en `{db_path}`")
    if st.button("🔄 Refrescar manualmente"):
        st.cache_data.clear()
        st.rerun()


# Auto-refresh sin bloquear
st.markdown(
    f"""<meta http-equiv="refresh" content="{refresh_seconds}">""",
    unsafe_allow_html=True,
)


# ── Cabecera ───────────────────────────────────────────────────────────────────

st.title("📊 FTMO Scalper — Overview")

snap = data.get_latest_snapshot(db_path)
closes = data.load_position_closes(db_path)

balance = snap["balance"] if snap else initial_balance
equity = snap["equity"] if snap else initial_balance
floating_pnl = equity - balance
n_open = int(snap["n_open_positions"]) if snap else 0

# Métricas FTMO
total_pnl = balance - initial_balance
total_pnl_pct = total_pnl / initial_balance * 100
target_eur = initial_balance * PROFIT_TARGET_PCT / 100
max_dd_eur = initial_balance * MAX_LOSS_LIMIT_PCT / 100
daily_dd_eur = initial_balance * DAILY_LOSS_LIMIT_PCT / 100

# Cabecera grande
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        "Balance",
        fmt.fmt_eur(balance),
        delta=fmt.fmt_eur(total_pnl, sign=True),
        help="Saldo actual sin posiciones flotantes",
    )
with c2:
    st.metric(
        "Equity",
        fmt.fmt_eur(equity),
        delta=fmt.fmt_eur(floating_pnl, sign=True) if floating_pnl != 0 else None,
        help="Balance + PnL flotante de posiciones abiertas",
    )
with c3:
    pct_to_target = (total_pnl / target_eur * 100) if target_eur > 0 else 0.0
    st.metric(
        "Profit Target",
        fmt.fmt_pct(pct_to_target, 1),
        delta=f"{fmt.fmt_eur(total_pnl)} / {fmt.fmt_eur(target_eur)}",
        help="Progreso hacia el objetivo del +10%",
    )
with c4:
    pct_dd_used = (max(0, -total_pnl) / max_dd_eur * 100) if max_dd_eur > 0 else 0.0
    st.metric(
        "Max DD usado",
        fmt.fmt_pct(pct_dd_used, 1),
        delta=f"-{fmt.fmt_eur(max(0, -total_pnl))} / {fmt.fmt_eur(max_dd_eur)}",
        delta_color="inverse",
        help=f"Máximo permitido: {MAX_LOSS_LIMIT_PCT}% = {fmt.fmt_eur(max_dd_eur)}",
    )


# ── Heartbeat del bot ──────────────────────────────────────────────────────────

st.divider()
hb_col, alerts_col = st.columns([1, 2])

with hb_col:
    st.subheader("🩺 Heartbeat")
    if health["exists"] and health["last_event_ts"] is not None:
        age = (datetime.now(timezone.utc) - health["last_event_ts"]).total_seconds()
        if age < HEARTBEAT_WARN_SECONDS:
            st.success(f"Bot ACTIVO — última actividad hace {fmt.fmt_duration(age)}")
        else:
            st.error(
                f"⚠️ Sin eventos hace {fmt.fmt_duration(age)} — verificar bot"
            )
    else:
        st.warning("Sin datos de eventos aún")

with alerts_col:
    st.subheader("🚨 Alertas activas")
    orders = data.load_orders(db_path)
    anomalies = metrics.detect_anomalies(closes, orders)
    if not anomalies:
        st.success("Sin anomalías detectadas")
    else:
        # Mostrar las 3 más severas
        sev_order = {"high": 0, "medium": 1, "low": 2}
        anomalies_sorted = sorted(anomalies, key=lambda a: sev_order.get(a["severity"], 99))
        for a in anomalies_sorted[:3]:
            st.warning(f"{fmt.severity_color(a['severity'])} **{a['title']}** — {a['detail']}")
        if len(anomalies) > 3:
            st.caption(f"+ {len(anomalies) - 3} más en la página 🚨 Anomalies")


# ── Posiciones abiertas ────────────────────────────────────────────────────────

st.divider()
st.subheader(f"💼 Posiciones abiertas ({n_open})")

# Buscamos órdenes recientes sin position_close emparejado
open_tickets = data.get_open_tickets(db_path)
if open_tickets and not orders.empty:
    open_orders = orders[orders["ticket"].isin(open_tickets)].sort_values("ts", ascending=False)
    if not open_orders.empty:
        display = open_orders[[
            "ts", "strategy_id", "symbol", "side", "ticket",
            "fill_price", "signal_sl", "signal_tp", "volume", "slippage_pips",
        ]].copy()
        display.columns = [
            "Hora", "Estrategia", "Par", "Side", "Ticket",
            "Entry", "SL", "TP", "Lotes", "Slip(pips)",
        ]
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("Hay tickets abiertos en MT5 pero no tenemos orden registrada — posiciones recuperadas o pre-bot")
else:
    st.info("Sin posiciones abiertas")


# ── Resumen del día ────────────────────────────────────────────────────────────

st.divider()
today = datetime.now(timezone.utc).date()
today_start_unix = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).timestamp()
today_closes = data.load_position_closes(db_path, since_unix=today_start_unix)

st.subheader(f"📅 Hoy ({today.isoformat()})")
day_summary = metrics.trade_summary(today_closes)

dc1, dc2, dc3, dc4 = st.columns(4)
with dc1:
    st.metric("Trades hoy", day_summary["n_trades"])
with dc2:
    st.metric("Win Rate hoy", fmt.fmt_pct(day_summary["win_rate"]))
with dc3:
    st.metric(
        "Net hoy",
        fmt.fmt_eur(day_summary["net_total"], sign=True),
        delta_color="off",
    )
with dc4:
    pct_daily = abs(min(0, day_summary["net_total"])) / daily_dd_eur * 100
    st.metric(
        "Daily DD usado",
        fmt.fmt_pct(pct_daily),
        delta=f"Límite {fmt.fmt_eur(daily_dd_eur)}",
        delta_color="inverse",
    )


# ── Curva de equity ────────────────────────────────────────────────────────────

st.divider()
st.subheader("📈 Curva de equity")

if not closes.empty:
    eq = metrics.equity_curve(closes, starting_balance=initial_balance)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq["close_time"], y=eq["equity"],
        mode="lines+markers",
        name="Equity",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=4),
        hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>" +
                      "Equity: €%{y:,.2f}<br>" +
                      "Trade: %{customdata[0]} %{customdata[1]}<br>" +
                      "Net: €%{customdata[2]:+,.2f}<extra></extra>",
        customdata=eq[["strategy_id", "symbol", "net"]].values,
    ))
    # Líneas de referencia FTMO
    fig.add_hline(y=initial_balance, line_dash="dash", line_color="gray",
                  annotation_text="Balance inicial", annotation_position="right")
    fig.add_hline(y=initial_balance + target_eur, line_dash="dot", line_color="green",
                  annotation_text=f"Target +{PROFIT_TARGET_PCT:.0f}%",
                  annotation_position="right")
    fig.add_hline(y=initial_balance - max_dd_eur, line_dash="dot", line_color="red",
                  annotation_text=f"Límite -{MAX_LOSS_LIMIT_PCT:.0f}%",
                  annotation_position="right")
    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        yaxis_title="Equity (€)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Aún no hay trades cerrados para mostrar equity")


# ── Footer ─────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    f"Auto-refresh cada {refresh_seconds}s · "
    f"Próximas páginas en el menú lateral: 🎯 Strategies · ⚙️ Execution · 📜 Trades · 🔍 Inspector · 🚨 Anomalies"
)
