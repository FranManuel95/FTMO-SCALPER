import os
import pandas as pd
import numpy as np


TRADES_PATH = "backtest/results/xau_m5_trades_SELL_ONLY_20241104_2100_20260410_1200_hours_9_15.csv"


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
        wins=("won_calc", "sum"),
        pnl=("pnl", "sum"),
        avg_pnl=("pnl", "mean"),
        avg_r=("pnl_r", "mean") if "pnl_r" in df.columns else ("pnl", "mean"),
    ).reset_index()

    out["losses"] = out["trades"] - out["wins"]
    out["win_rate"] = (out["wins"] / out["trades"] * 100).round(2)

    pf_vals = []
    avg_win_vals = []
    avg_loss_vals = []

    for _, g in grouped:
        pnls = g["pnl"]
        pf_vals.append(round(safe_profit_factor(pnls), 3))

        pos = pnls[pnls > 0]
        neg = pnls[pnls <= 0]

        avg_win_vals.append(round(float(pos.mean()) if len(pos) else 0.0, 2))
        avg_loss_vals.append(round(abs(float(neg.mean())) if len(neg) else 0.0, 2))

    out["profit_factor"] = pf_vals
    out["avg_win"] = avg_win_vals
    out["avg_loss"] = avg_loss_vals

    return out


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

    for col in ["entry_time", "exit_time", "signal_time"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # columna auxiliar universal
    df["won_calc"] = df["pnl"] > 0

    if "month" in df.columns:
        month_map = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
            5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
            9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
        df["month_name"] = df["month"].map(month_map)

    if "weekday" in df.columns:
        weekday_map = {
            0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
        }
        df["weekday_name"] = df["weekday"].map(weekday_map)

    if "bars_held" in df.columns:
        bars_bins = [0, 3, 6, 12, 18, 24, 36, 9999]
        bars_labels = ["1-3", "4-6", "7-12", "13-18", "19-24", "25-36", "37+"]
        df["bars_bucket"] = pd.cut(df["bars_held"], bins=bars_bins, labels=bars_labels, right=True)

    if "entry_hour" in df.columns:
        df["entry_hour"] = df["entry_hour"].astype("Int64")

    print("\n=== RESUMEN GENERAL CSV ===")
    print(f"Trades totales: {len(df)}")
    if "exit_reason" in df.columns:
        print(df["exit_reason"].value_counts().to_string())

    timeout_df = df[df["exit_reason"].astype(str).str.lower() == "timeout"].copy()

    if timeout_df.empty:
        print("\nNo hay trades con exit_reason='timeout'.")
        return

    print("\n" + "=" * 90)
    print("ANÁLISIS PROFUNDO DE TIMEOUTS")
    print("=" * 90)

    total_timeouts = len(timeout_df)
    timeout_wins = int((timeout_df["pnl"] > 0).sum())
    timeout_losses = total_timeouts - timeout_wins
    timeout_wr = timeout_wins / total_timeouts * 100
    timeout_pf = safe_profit_factor(timeout_df["pnl"])

    print(f"Timeouts totales:      {total_timeouts}")
    print(f"Timeouts ganadores:    {timeout_wins}")
    print(f"Timeouts perdedores:   {timeout_losses}")
    print(f"Win rate timeout:      {timeout_wr:.2f}%")
    print(f"PnL total timeout:     {timeout_df['pnl'].sum():.2f}")
    print(f"Avg pnl timeout:       {timeout_df['pnl'].mean():.2f}")
    print(f"Profit factor timeout: {timeout_pf:.3f}")

    timeout_df["timeout_sign"] = np.where(timeout_df["pnl"] > 0, "timeout_win", "timeout_loss")
    print_block("TIMEOUTS POR SIGNO", build_summary(timeout_df, "timeout_sign"), sort_by="pnl", ascending=False)

    if "month_name" in timeout_df.columns:
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        tmp = build_summary(timeout_df, "month_name")
        tmp["month_name"] = pd.Categorical(tmp["month_name"], categories=month_order, ordered=True)
        print_block("TIMEOUTS POR MES", tmp, sort_by="month_name", ascending=True)

    if "entry_hour" in timeout_df.columns:
        print_block("TIMEOUTS POR HORA", build_summary(timeout_df, "entry_hour"), sort_by="entry_hour", ascending=True)

    if "weekday_name" in timeout_df.columns:
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        tmp = build_summary(timeout_df, "weekday_name")
        tmp["weekday_name"] = pd.Categorical(tmp["weekday_name"], categories=weekday_order, ordered=True)
        print_block("TIMEOUTS POR DÍA", tmp, sort_by="weekday_name", ascending=True)

    if "bars_bucket" in timeout_df.columns:
        print_block("TIMEOUTS POR DURACIÓN", build_summary(timeout_df, "bars_bucket"), sort_by="bars_bucket", ascending=True)

    df["is_timeout"] = np.where(df["exit_reason"].astype(str).str.lower() == "timeout", "timeout", "non_timeout")
    print_block("TIMEOUT VS NO TIMEOUT", build_summary(df, "is_timeout"), sort_by="pnl", ascending=False)

    wanted_cols = [
        c for c in [
            "entry_time", "exit_time", "entry_hour", "weekday", "month",
            "bars_held", "pnl", "pnl_r", "exit_reason"
        ] if c in timeout_df.columns
    ]

    print_block("TOP 10 TIMEOUTS", timeout_df.sort_values("pnl", ascending=False)[wanted_cols].head(10))
    print_block("BOTTOM 10 TIMEOUTS", timeout_df.sort_values("pnl", ascending=True)[wanted_cols].head(10))

    print("\n=== PISTAS RÁPIDAS ===")
    sign_summary = build_summary(timeout_df, "timeout_sign").sort_values("pnl", ascending=False)
    best_sign = sign_summary.iloc[0]
    worst_sign = sign_summary.iloc[-1]
    print(
        f"Mejor grupo timeout: {best_sign['timeout_sign']} | trades={int(best_sign['trades'])} "
        f"| pnl={best_sign['pnl']:.2f} | pf={best_sign['profit_factor']:.3f}"
    )
    print(
        f"Peor grupo timeout:  {worst_sign['timeout_sign']} | trades={int(worst_sign['trades'])} "
        f"| pnl={worst_sign['pnl']:.2f} | pf={worst_sign['profit_factor']:.3f}"
    )

    if "entry_hour" in timeout_df.columns:
        hour_summary = build_summary(timeout_df, "entry_hour").sort_values("pnl", ascending=False)
        best_hour = hour_summary.iloc[0]
        worst_hour = hour_summary.iloc[-1]
        print(
            f"Mejor hora timeout: {int(best_hour['entry_hour'])} | trades={int(best_hour['trades'])} "
            f"| pnl={best_hour['pnl']:.2f} | pf={best_hour['profit_factor']:.3f}"
        )
        print(
            f"Peor hora timeout:  {int(worst_hour['entry_hour'])} | trades={int(worst_hour['trades'])} "
            f"| pnl={worst_hour['pnl']:.2f} | pf={worst_hour['profit_factor']:.3f}"
        )

    if "bars_bucket" in timeout_df.columns:
        dur_summary = build_summary(timeout_df, "bars_bucket").sort_values("pnl", ascending=False)
        best_dur = dur_summary.iloc[0]
        worst_dur = dur_summary.iloc[-1]
        print(
            f"Mejor duración timeout: {best_dur['bars_bucket']} | trades={int(best_dur['trades'])} "
            f"| pnl={best_dur['pnl']:.2f} | pf={best_dur['profit_factor']:.3f}"
        )
        print(
            f"Peor duración timeout:  {worst_dur['bars_bucket']} | trades={int(worst_dur['trades'])} "
            f"| pnl={worst_dur['pnl']:.2f} | pf={worst_dur['profit_factor']:.3f}"
        )


if __name__ == "__main__":
    main()