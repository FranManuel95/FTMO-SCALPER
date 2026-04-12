import os
import numpy as np
import pandas as pd


TRADES_PATH = "backtest/results/gbpusd_gbp_strategy_trades.csv"


def safe_profit_factor(pnls: pd.Series) -> float:
    gp = float(pnls[pnls > 0].sum())
    gl = abs(float(pnls[pnls <= 0].sum()))
    if gl <= 1e-10:
        return 999.0 if gp > 0 else 0.0
    return gp / gl


def build_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    grouped = df.groupby(group_col, dropna=False)

    out = grouped.agg(
        trades=("pnl", "count"),
        wins=("won", "sum"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        avg_r=("pnl_r", "mean"),
        avg_bars=("bars_held", "mean"),
    ).reset_index()

    out["losses"] = out["trades"] - out["wins"]
    out["win_rate"] = (out["wins"] / out["trades"] * 100).round(2)

    pf_list = []
    avg_win_list = []
    avg_loss_list = []

    for _, g in grouped:
        pnls = g["pnl"]
        pf_list.append(round(safe_profit_factor(pnls), 3))

        pos = pnls[pnls > 0]
        neg = pnls[pnls <= 0]

        avg_win_list.append(round(float(pos.mean()) if len(pos) else 0.0, 2))
        avg_loss_list.append(round(abs(float(neg.mean())) if len(neg) else 0.0, 2))

    out["profit_factor"] = pf_list
    out["avg_win"] = avg_win_list
    out["avg_loss"] = avg_loss_list

    cols = [
        group_col,
        "trades",
        "wins",
        "losses",
        "win_rate",
        "pnl",
        "avg_pnl",
        "avg_r",
        "profit_factor",
        "avg_win",
        "avg_loss",
        "avg_bars",
    ]
    return out[cols]


def print_block(title: str, df: pd.DataFrame, sort_by: str = None, ascending: bool = False):
    print(f"\n=== {title} ===")
    if df.empty:
        print("Sin datos")
        return

    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)

    print(df.to_string(index=False))


def main():
    if not os.path.exists(TRADES_PATH):
        raise FileNotFoundError(f"No existe el archivo: {TRADES_PATH}")

    df = pd.read_csv(TRADES_PATH)

    if df.empty:
        raise ValueError("El CSV está vacío.")

    # Parseos
    for col in ["signal_time", "entry_time", "exit_time"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "entry_date" in df.columns:
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
    if "exit_date" in df.columns:
        df["exit_date"] = pd.to_datetime(df["exit_date"], errors="coerce")

    # Normalizaciones
    if "won" in df.columns:
        if df["won"].dtype != bool:
            df["won"] = df["won"].astype(str).str.lower().map(
                {"true": True, "false": False}
            )
            df["won"] = df["won"].fillna(df["pnl"] > 0)

    # Buckets ADX
    if "adx" in df.columns:
        adx_bins = [0, 20, 25, 30, 35, 40, 50, 60, 1000]
        adx_labels = ["0-20", "20-25", "25-30", "30-35", "35-40", "40-50", "50-60", "60+"]
        df["adx_bucket"] = pd.cut(df["adx"], bins=adx_bins, labels=adx_labels, right=False)

    # Buckets ATR por cuantiles
    if "atr" in df.columns and df["atr"].nunique() >= 4:
        df["atr_quartile"] = pd.qcut(
            df["atr"],
            q=4,
            labels=["Q1_low", "Q2", "Q3", "Q4_high"],
            duplicates="drop"
        )
    else:
        df["atr_quartile"] = "unknown"

    # Buckets duración
    if "bars_held" in df.columns:
        bars_bins = [0, 3, 6, 12, 18, 24, 30, 9999]
        bars_labels = ["1-3", "4-6", "7-12", "13-18", "19-24", "25-30", "31+"]
        df["bars_bucket"] = pd.cut(df["bars_held"], bins=bars_bins, labels=bars_labels, right=True)

    # Buckets hora
    if "entry_hour" in df.columns:
        hour_bins = [0, 7, 9, 11, 13, 15, 17, 24]
        hour_labels = ["00-06", "07-08", "09-10", "11-12", "13-14", "15-16", "17-23"]
        df["hour_bucket"] = pd.cut(df["entry_hour"], bins=hour_bins, labels=hour_labels, right=False)

    weekday_map = {
        0: "Mon",
        1: "Tue",
        2: "Wed",
        3: "Thu",
        4: "Fri",
        5: "Sat",
        6: "Sun",
    }
    if "weekday" in df.columns:
        df["weekday_name"] = df["weekday"].map(weekday_map)

    month_map = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    if "month" in df.columns:
        df["month_name"] = df["month"].map(month_map)

    # Resumen general
    total_trades = len(df)
    wins = int((df["pnl"] > 0).sum())
    losses = total_trades - wins
    win_rate = wins / total_trades * 100
    total_pnl = float(df["pnl"].sum())
    avg_pnl = float(df["pnl"].mean())
    avg_r = float(df["pnl_r"].mean()) if "pnl_r" in df.columns else np.nan
    pf = safe_profit_factor(df["pnl"])

    print("\n=== RESUMEN GENERAL ===")
    print(f"Trades:        {total_trades}")
    print(f"Wins:          {wins}")
    print(f"Losses:        {losses}")
    print(f"Win rate:      {win_rate:.2f}%")
    print(f"PnL total:     {total_pnl:.2f}")
    print(f"Avg pnl:       {avg_pnl:.2f}")
    print(f"Avg R:         {avg_r:.4f}")
    print(f"Profit factor: {pf:.3f}")

    if "exit_reason" in df.columns:
        print("\n=== EXIT REASONS ===")
        print(df["exit_reason"].value_counts().to_string())

    # Análisis principales
    if "side" in df.columns:
        print_block("POR LADO", build_summary(df, "side"), sort_by="pnl", ascending=False)

    if "entry_hour" in df.columns:
        print_block("POR HORA DE ENTRADA", build_summary(df, "entry_hour"), sort_by="entry_hour", ascending=True)

    if "hour_bucket" in df.columns:
        print_block("POR FRANJA HORARIA", build_summary(df, "hour_bucket"), sort_by="hour_bucket", ascending=True)

    if "weekday_name" in df.columns:
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        tmp = build_summary(df, "weekday_name")
        tmp["weekday_name"] = pd.Categorical(tmp["weekday_name"], categories=weekday_order, ordered=True)
        print_block("POR DIA DE LA SEMANA", tmp, sort_by="weekday_name", ascending=True)

    if "month_name" in df.columns:
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        tmp = build_summary(df, "month_name")
        tmp["month_name"] = pd.Categorical(tmp["month_name"], categories=month_order, ordered=True)
        print_block("POR MES", tmp, sort_by="month_name", ascending=True)

    if "adx_bucket" in df.columns:
        print_block("POR BUCKET ADX", build_summary(df, "adx_bucket"), sort_by="adx_bucket", ascending=True)

    if "atr_quartile" in df.columns:
        print_block("POR CUARTIL ATR", build_summary(df, "atr_quartile"), sort_by="atr_quartile", ascending=True)

    if "bars_bucket" in df.columns:
        print_block("POR DURACION (BARS)", build_summary(df, "bars_bucket"), sort_by="bars_bucket", ascending=True)

    # Top / Bottom
    print_block(
        "TOP 15 TRADES",
        df.sort_values("pnl", ascending=False)[[
            "entry_time", "exit_time", "side", "entry_hour", "weekday",
            "month", "adx", "atr", "bars_held", "exit_reason", "pnl", "pnl_r"
        ]].head(15)
    )

    print_block(
        "BOTTOM 15 TRADES",
        df.sort_values("pnl", ascending=True)[[
            "entry_time", "exit_time", "side", "entry_hour", "weekday",
            "month", "adx", "atr", "bars_held", "exit_reason", "pnl", "pnl_r"
        ]].head(15)
    )

    # Combinación lado + franja
    if "side" in df.columns and "hour_bucket" in df.columns:
        combo = (
            df.groupby(["side", "hour_bucket"], dropna=False)
            .agg(
                trades=("pnl", "count"),
                wins=("won", "sum"),
                pnl=("pnl", "sum"),
                avg_r=("pnl_r", "mean"),
            )
            .reset_index()
        )
        combo["win_rate"] = (combo["wins"] / combo["trades"] * 100).round(2)

        pf_vals = []
        for _, g in df.groupby(["side", "hour_bucket"], dropna=False):
            pf_vals.append(round(safe_profit_factor(g["pnl"]), 3))
        combo["profit_factor"] = pf_vals

        print_block("SIDE + FRANJA HORARIA", combo, sort_by="pnl", ascending=False)

    # Filtros potenciales candidatos
    print("\n=== POSIBLES PISTAS ===")
    if "side" in df.columns:
        side_summary = build_summary(df, "side").sort_values("pnl", ascending=False)
        best_side = side_summary.iloc[0]
        print(
            f"Mejor lado: {best_side['side']} | trades={int(best_side['trades'])} "
            f"| pnl={best_side['pnl']:.2f} | pf={best_side['profit_factor']:.3f}"
        )

    if "hour_bucket" in df.columns:
        hour_summary = build_summary(df, "hour_bucket").sort_values("pnl", ascending=False)
        best_hour = hour_summary.iloc[0]
        worst_hour = hour_summary.iloc[-1]
        print(
            f"Mejor franja: {best_hour['hour_bucket']} | trades={int(best_hour['trades'])} "
            f"| pnl={best_hour['pnl']:.2f} | pf={best_hour['profit_factor']:.3f}"
        )
        print(
            f"Peor franja:  {worst_hour['hour_bucket']} | trades={int(worst_hour['trades'])} "
            f"| pnl={worst_hour['pnl']:.2f} | pf={worst_hour['profit_factor']:.3f}"
        )

    if "adx_bucket" in df.columns:
        adx_summary = build_summary(df, "adx_bucket").sort_values("pnl", ascending=False)
        best_adx = adx_summary.iloc[0]
        print(
            f"Mejor bucket ADX: {best_adx['adx_bucket']} | trades={int(best_adx['trades'])} "
            f"| pnl={best_adx['pnl']:.2f} | pf={best_adx['profit_factor']:.3f}"
        )

    if "atr_quartile" in df.columns:
        atr_summary = build_summary(df, "atr_quartile").sort_values("pnl", ascending=False)
        best_atr = atr_summary.iloc[0]
        print(
            f"Mejor cuartil ATR: {best_atr['atr_quartile']} | trades={int(best_atr['trades'])} "
            f"| pnl={best_atr['pnl']:.2f} | pf={best_atr['profit_factor']:.3f}"
        )


if __name__ == "__main__":
    main()