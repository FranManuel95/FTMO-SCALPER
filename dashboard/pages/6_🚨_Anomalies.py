"""
Página Anomalies — detección automática de comportamientos sospechosos.

Reglas:
  - Quick-stop rate > 50% (indica falsos breakouts o trail demasiado agresivo)
  - Rachas de 4+ pérdidas consecutivas
  - Slippage Z-score > 2.5
  - Lot size con desviación > 3σ del histórico (potencial bug de sizing)

Cada anomalía tiene severidad (high/medium/low) con recomendación de acción.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from dashboard.lib import data, metrics, formatting as fmt


st.set_page_config(page_title="Anomalies", page_icon="🚨", layout="wide")
st.title("🚨 Anomaly Detection")

DB_PATH = os.environ.get("FTMO_EVENTS_DB", "data/events.db")
with st.sidebar:
    db_path = st.text_input("Ruta SQLite", DB_PATH)
    days_lookback = st.slider("Lookback (días)", 1, 90, 30)

since_unix = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_lookback)).timestamp()
closes = data.load_position_closes(db_path, since_unix=since_unix)
orders = data.load_orders(db_path, since_unix=since_unix)

anomalies = metrics.detect_anomalies(closes, orders)

# ── Resumen ────────────────────────────────────────────────────────────────────

if not anomalies:
    st.success("✅ Sin anomalías detectadas en el periodo")
    st.stop()

high = [a for a in anomalies if a["severity"] == "high"]
medium = [a for a in anomalies if a["severity"] == "medium"]
low = [a for a in anomalies if a["severity"] == "low"]

c1, c2, c3 = st.columns(3)
c1.metric("🔴 Severidad alta", len(high))
c2.metric("🟡 Severidad media", len(medium))
c3.metric("🔵 Severidad baja", len(low))

st.divider()


# ── Listado por severidad ──────────────────────────────────────────────────────

def render_anomaly(a: dict) -> None:
    color = fmt.severity_color(a["severity"])
    cat = a["category"].replace("_", " ").title()
    with st.container(border=True):
        st.markdown(f"### {color} {a['title']}")
        st.caption(f"Categoría: **{cat}** · Severidad: **{a['severity']}**")
        st.write(a["detail"])
        # Sugerencias por categoría
        suggestions = {
            "quick_stops": "→ Revisar el spread del par en hora de entrada. Considerar filtro de desviación o ampliar SL.",
            "losing_streak": "→ Si la racha continúa 2 semanas más, pausar la estrategia. Verificar si hay cambio de régimen.",
            "slippage": "→ Verificar broker/spread. Posible deterioro de ejecución.",
            "lot_size": "→ ALARMA: posible bug de position sizing. Revisar `_compute_volume` para este símbolo.",
        }
        if a["category"] in suggestions:
            st.info(suggestions[a["category"]])


if high:
    st.subheader("🔴 Severidad alta")
    for a in high:
        render_anomaly(a)

if medium:
    st.subheader("🟡 Severidad media")
    for a in medium:
        render_anomaly(a)

if low:
    st.subheader("🔵 Severidad baja")
    for a in low:
        render_anomaly(a)
