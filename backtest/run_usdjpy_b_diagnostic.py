# backtest/run_usdjpy_b_diagnostic.py
# Analiza los trades de Estrategia B para identificar POR QUÉ pierde.
# Ejecutar: python -m backtest.run_usdjpy_b_diagnostic

import pandas as pd
import numpy as np
from pathlib import Path

trades = pd.read_csv("backtest/results/usdjpy_b_trades.csv", parse_dates=["entry_time"])

print(f"Total trades: {len(trades)}")
print(f"Win rate global: {trades['won'].mean():.2%}\n")

# ─── 1. WIN RATE POR DIRECCIÓN ───────────────────────────────────────────────
print("=== WIN RATE POR DIRECCIÓN ===")
print(trades.groupby("signal")[["won"]].agg(
    trades=("won","count"), wins=("won","sum"),
    wr=("won","mean"), avg_pnl=("pnl","mean")
).round(3).to_string())

# ─── 2. WIN RATE POR BIAS DEL DÍA ────────────────────────────────────────────
print("\n=== WIN RATE POR BIAS DEL DÍA ===")
print(trades.groupby("bias")[["won"]].agg(
    trades=("won","count"), wins=("won","sum"),
    wr=("won","mean"), avg_pnl=("pnl","mean")
).round(3).to_string())

# ─── 3. WIN RATE POR CUARTIL DE ADX ─────────────────────────────────────────
print("\n=== WIN RATE POR NIVEL DE ADX ===")
trades["adx_bucket"] = pd.cut(trades["adx"],
    bins=[0, 15, 20, 25, 30, 40, 60],
    labels=["<15","15-20","20-25","25-30","30-40",">40"])
print(trades.groupby("adx_bucket", observed=True).agg(
    trades=("won","count"), wr=("won","mean"), avg_pnl=("pnl","mean")
).round(3).to_string())

# ─── 4. WIN RATE POR HORA DE ENTRADA ─────────────────────────────────────────
print("\n=== WIN RATE POR HORA UTC ===")
trades["hour"] = trades["entry_time"].dt.hour
print(trades.groupby("hour").agg(
    trades=("won","count"), wr=("won","mean"), avg_pnl=("pnl","mean")
).round(3).to_string())

# ─── 5. WIN RATE POR DURACIÓN (BARS HELD) ────────────────────────────────────
print("\n=== WIN RATE POR DURACIÓN ===")
trades["bars_bucket"] = pd.cut(trades["bars_held"],
    bins=[0,5,10,15,20,30,50],
    labels=["1-5","6-10","11-15","16-20","21-30","31+"])
print(trades.groupby("bars_bucket", observed=True).agg(
    trades=("won","count"), wr=("won","mean"), avg_pnl=("pnl","mean")
).round(3).to_string())

# ─── 6. DIAGNÓSTICO DE DIRECCIÓN vs BIAS ─────────────────────────────────────
print("\n=== SIGNAL vs BIAS (debería ser siempre igual) ===")
ok   = trades[trades["signal"] == trades["bias"].map({"BULL":"BUY","BEAR":"SELL"})]
diff = trades[trades["signal"] != trades["bias"].map({"BULL":"BUY","BEAR":"SELL"})]
print(f"  Alineados bias=señal : {len(ok)} trades | WR {ok['won'].mean():.2%}")
print(f"  Desalineados         : {len(diff)} trades")

# ─── 7. PEORES RACHAS ────────────────────────────────────────────────────────
print("\n=== TOP 5 RACHAS PERDEDORAS ===")
streak = cur = 0
best_streak_trades = []
cur_trades = []
for _, row in trades.iterrows():
    if row["pnl"] < 0:
        cur += 1
        cur_trades.append(row)
        if cur > streak:
            streak = cur
            best_streak_trades = cur_trades.copy()
    else:
        cur = 0
        cur_trades = []
print(f"  Máxima racha: {streak} pérdidas seguidas")
if best_streak_trades:
    df_streak = pd.DataFrame(best_streak_trades)
    print(f"  Período: {df_streak['entry_time'].iloc[0]} → {df_streak['entry_time'].iloc[-1]}")
    print(f"  ADX medio en racha: {df_streak['adx'].mean():.1f}")
    print(f"  Señales: {df_streak['signal'].value_counts().to_dict()}")

# ─── 8. RESUMEN ACCIONABLE ───────────────────────────────────────────────────
print("\n=== RESUMEN ACCIONABLE ===")
wr_by_adx = trades.groupby("adx_bucket", observed=True)["won"].mean()
best_adx = wr_by_adx[wr_by_adx >= 0.45]
print(f"  Buckets ADX con WR≥45%: {list(best_adx.index)}")

wr_by_hour = trades.groupby("hour")["won"].mean()
best_hours = wr_by_hour[wr_by_hour >= 0.45]
print(f"  Horas UTC con WR≥45%:   {list(best_hours.index)}")

wr_by_dir = trades.groupby("signal")["won"].mean()
print(f"  Dirección más rentable: {wr_by_dir.idxmax()} ({wr_by_dir.max():.2%})")
