"""
Cálculos de métricas a partir de DataFrames cargados por lib.data.

Todas las funciones son puras: reciben un DataFrame, devuelven números o
DataFrames de resumen. No tocan el disco.
"""
from __future__ import annotations

import pandas as pd


# ── Métricas globales ──────────────────────────────────────────────────────────

def trade_summary(closes: pd.DataFrame) -> dict:
    """Métricas top-level del histórico de trades cerrados."""
    if closes.empty:
        return _empty_summary()

    net = closes["net"].fillna(closes["pnl"])
    winners = closes[net > 0]
    losers = closes[net < 0]
    gross_profit = winners["net"].sum() if not winners.empty else 0.0
    gross_loss = -losers["net"].sum() if not losers.empty else 0.0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
    expectancy = net.mean() if len(net) else 0.0
    avg_winner = winners["net"].mean() if not winners.empty else 0.0
    avg_loser = losers["net"].mean() if not losers.empty else 0.0
    wr = len(winners) / len(closes) * 100 if len(closes) else 0.0

    # Max drawdown sobre la curva acumulada de net
    cum = net.cumsum()
    running_max = cum.cummax()
    dd = (cum - running_max).min()  # negativo

    return {
        "n_trades": len(closes),
        "n_winners": len(winners),
        "n_losers": len(losers),
        "win_rate": wr,
        "net_total": float(net.sum()),
        "gross_profit": float(gross_profit),
        "gross_loss": float(gross_loss),
        "profit_factor": float(pf) if pf != float("inf") else 999.0,
        "expectancy": float(expectancy),
        "avg_winner": float(avg_winner),
        "avg_loser": float(avg_loser),
        "max_dd": float(dd) if pd.notna(dd) else 0.0,
        "total_commission": float(closes["commission"].sum()) if "commission" in closes else 0.0,
    }


def _empty_summary() -> dict:
    return {
        "n_trades": 0, "n_winners": 0, "n_losers": 0, "win_rate": 0.0,
        "net_total": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
        "profit_factor": 0.0, "expectancy": 0.0,
        "avg_winner": 0.0, "avg_loser": 0.0,
        "max_dd": 0.0, "total_commission": 0.0,
    }


# ── Por estrategia ─────────────────────────────────────────────────────────────

def per_strategy_stats(closes: pd.DataFrame) -> pd.DataFrame:
    """Tabla con una fila por estrategia y métricas claves."""
    if closes.empty:
        return pd.DataFrame()
    rows = []
    for strat, g in closes.groupby("strategy_id"):
        s = trade_summary(g)
        s["strategy_id"] = strat
        s["last_trade_ts"] = g["close_time"].max()
        rows.append(s)
    out = pd.DataFrame(rows).set_index("strategy_id")
    cols = ["n_trades", "n_winners", "n_losers", "win_rate",
            "profit_factor", "net_total", "expectancy", "max_dd",
            "avg_winner", "avg_loser", "total_commission", "last_trade_ts"]
    return out.reindex(columns=[c for c in cols if c in out.columns])


def equity_curve(closes: pd.DataFrame, starting_balance: float = 0.0) -> pd.DataFrame:
    """Curva acumulada de equity desde balance inicial."""
    if closes.empty:
        return pd.DataFrame(columns=["close_time", "cum_net", "equity"])
    df = closes.sort_values("close_time").copy()
    df["cum_net"] = df["net"].fillna(df["pnl"]).cumsum()
    df["equity"] = starting_balance + df["cum_net"]
    return df[["close_time", "ticket", "strategy_id", "symbol", "net", "cum_net", "equity"]]


# ── Funnel de señales ──────────────────────────────────────────────────────────

def signal_funnel(signals: pd.DataFrame, by: str = "strategy_id") -> pd.DataFrame:
    """Cuántas señales se generaron, cuántas se ejecutaron, y por qué se rechazaron."""
    if signals.empty:
        return pd.DataFrame()
    grouped = signals.groupby(by)
    out = pd.DataFrame({
        "total": grouped.size(),
        "executed": grouped["was_executed"].sum(),
    })
    out["rejected"] = out["total"] - out["executed"]
    out["execution_rate"] = (out["executed"] / out["total"] * 100).round(1)
    return out


def rejection_reasons(signals: pd.DataFrame) -> pd.DataFrame:
    """Tabla con conteo de rechazos por motivo."""
    rejected = signals[~signals["was_executed"].fillna(False)] if "was_executed" in signals else pd.DataFrame()
    if rejected.empty or "filter_reason" not in rejected.columns:
        return pd.DataFrame()
    return rejected["filter_reason"].value_counts().rename_axis("reason").reset_index(name="count")


# ── Calidad de ejecución ───────────────────────────────────────────────────────

def slippage_stats(orders: pd.DataFrame) -> pd.DataFrame:
    """Estadísticas de slippage por símbolo."""
    if orders.empty or "slippage_pips" not in orders.columns:
        return pd.DataFrame()
    df = orders.dropna(subset=["slippage_pips"])
    if df.empty:
        return pd.DataFrame()
    out = df.groupby("symbol")["slippage_pips"].agg(["count", "mean", "median", "std", "min", "max"])
    return out.round(2)


def quick_stop_rate(closes: pd.DataFrame, threshold_seconds: int = 300) -> pd.DataFrame:
    """Trades que se cerraron en < threshold (default 5 min) por estrategia."""
    if closes.empty or "duration_seconds" not in closes.columns:
        return pd.DataFrame()
    df = closes.dropna(subset=["duration_seconds"]).copy()
    df["is_quick"] = df["duration_seconds"] < threshold_seconds
    out = df.groupby("strategy_id").agg(
        total=("ticket", "count"),
        quick=("is_quick", "sum"),
    )
    out["quick_pct"] = (out["quick"] / out["total"] * 100).round(1)
    return out.sort_values("quick_pct", ascending=False)


# ── Drift detection ────────────────────────────────────────────────────────────

def recent_vs_historical_wr(closes: pd.DataFrame, recent_n: int = 10) -> pd.DataFrame:
    """Para cada estrategia: WR de últimos N trades vs WR histórico."""
    if closes.empty:
        return pd.DataFrame()
    rows = []
    for strat, g in closes.groupby("strategy_id"):
        if len(g) < 3:
            continue
        net = g.sort_values("close_time")["net"].fillna(g["pnl"])
        wr_all = (net > 0).mean() * 100
        wr_recent = (net.tail(recent_n) > 0).mean() * 100
        rows.append({
            "strategy_id": strat,
            "wr_all": round(wr_all, 1),
            "wr_recent": round(wr_recent, 1),
            "delta": round(wr_recent - wr_all, 1),
            "n_total": len(g),
            "n_recent": min(recent_n, len(g)),
        })
    return pd.DataFrame(rows).set_index("strategy_id")


# ── Anomalías ──────────────────────────────────────────────────────────────────

def detect_anomalies(closes: pd.DataFrame, orders: pd.DataFrame) -> list[dict]:
    """Devuelve lista de anomalías detectadas con su severidad."""
    anomalies: list[dict] = []
    if closes.empty:
        return anomalies

    # 1. Quick stop rate alto
    qs = quick_stop_rate(closes)
    for strat, row in qs.iterrows():
        if row["quick_pct"] > 50 and row["total"] >= 3:
            n_quick = int(row["quick"])
            n_total = int(row["total"])
            anomalies.append({
                "severity": "high" if row["quick_pct"] > 70 else "medium",
                "category": "quick_stops",
                "title": f"{strat}: {row['quick_pct']:.0f}% trades cierran en < 5 min",
                "detail": f"{n_quick}/{n_total} trades. Posible falso breakout o trail demasiado agresivo.",
            })

    # 2. Estrategia con racha de pérdidas
    for strat, g in closes.groupby("strategy_id"):
        if len(g) < 4:
            continue
        net = g.sort_values("close_time")["net"].fillna(g["pnl"])
        last_n = net.tail(4)
        if (last_n < 0).all():
            anomalies.append({
                "severity": "medium",
                "category": "losing_streak",
                "title": f"{strat}: 4 pérdidas consecutivas",
                "detail": f"Net últimos 4: €{last_n.sum():.2f}. Considerar pausar si continúa.",
            })

    # 3. Slippage anómalo
    if not orders.empty and "slippage_pips" in orders.columns:
        sl_df = orders.dropna(subset=["slippage_pips"])
        for symbol, g in sl_df.groupby("symbol"):
            if len(g) < 5:
                continue
            mean = g["slippage_pips"].mean()
            std = g["slippage_pips"].std() or 1.0
            recent = g.sort_values("ts").tail(3)
            for _, row in recent.iterrows():
                z = abs(row["slippage_pips"] - mean) / std
                if z > 2.5:
                    anomalies.append({
                        "severity": "low",
                        "category": "slippage",
                        "title": f"{symbol}: slippage anómalo {row['slippage_pips']:+.1f} pips",
                        "detail": f"Media histórica {mean:.1f} ± {std:.1f}. Z-score {z:.1f}.",
                    })
                    break

    # 4. Lot size desviado de lo "normal"
    if not orders.empty:
        for strat_sym, g in orders.groupby(["strategy_id", "symbol"]):
            if len(g) < 5:
                continue
            vols = pd.to_numeric(g["volume"], errors="coerce").dropna()
            if len(vols) < 5:
                continue
            mean = vols.mean()
            std = vols.std() or 1.0
            recent = vols.tail(1).iloc[0]
            if abs(recent - mean) / std > 3:
                anomalies.append({
                    "severity": "high",
                    "category": "lot_size",
                    "title": f"{strat_sym[0]}/{strat_sym[1]}: lote anómalo {recent:.2f}",
                    "detail": f"Media histórica {mean:.2f} ± {std:.2f}. Posible bug de sizing.",
                })

    return anomalies
