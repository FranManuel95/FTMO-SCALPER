import os
import pandas as pd

from backtest.backtester_gbp import GBPBacktester


START_DATE = "2025-04-01"
END_DATE = "2025-08-31"


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


def run_p2_and_export():
    bt = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.4,
        atr_sl_mult=1.0,
        symbol="GBPUSD",
        export_trades=False,
        session_start=8,
        session_end=14,
        adx_min=30,
        adx_max=38,
        trade_mode="SELL_ONLY",
    )

    df = bt.load_data()
    df = df.loc[(df.index >= pd.Timestamp(START_DATE)) & (df.index <= pd.Timestamp(END_DATE))].copy()

    if df.empty:
        raise ValueError("No hay datos en el rango P2.")

    bt.load_data = lambda: df
    result = bt.run()

    print(f"\n=== RESULTADO P2 SETUP GANADOR ===")
    print(f"Total trades:   {result.total_trades}")
    print(f"Winning trades: {result.winning_trades}")
    print(f"Losing trades:  {result.losing_trades}")
    print(f"Win rate:       {result.win_rate * 100:.2f}%")
    print(f"Profit factor:  {result.profit_factor}")
    print(f"Sharpe:         {result.sharpe_ratio}")
    print(f"Sortino:        {result.sortino_ratio}")
    print(f"Max drawdown:   {result.max_drawdown * 100:.2f}%")
    print(f"Total return:   {result.total_return * 100:.2f}%")
    print(f"Avg win:        {result.avg_win}")
    print(f"Avg loss:       {result.avg_loss}")
    print(f"Expectancy:     {result.expectancy}")

    # reconstruimos trades exportables usando el csv temporal del backtester si hiciera falta
    # como export_trades=False, repetimos una vez con export=True para guardar el detalle
    bt_export = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.4,
        atr_sl_mult=1.0,
        symbol="GBPUSD",
        export_trades=True,
        session_start=8,
        session_end=14,
        adx_min=30,
        adx_max=38,
        trade_mode="SELL_ONLY",
    )
    bt_export.load_data = lambda: df
    bt_export.run()

    src = "backtest/results/gbpusd_gbp_strategy_trades.csv"
    dst = "backtest/results/gbpusd_p2_setup_trades.csv"

    os.replace(src, dst)
    print(f"\nCSV P2 guardado en: {dst}")

    return dst


def main():
    csv_path = run_p2_and_export()
    df = pd.read_csv(csv_path)

    for col in ["signal_time", "entry_time", "exit_time"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "won" in df.columns and df["won"].dtype != bool:
        df["won"] = df["won"].astype(str).str.lower().map({"true": True, "false": False})
        df["won"] = df["won"].fillna(df["pnl"] > 0)

    month_map = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    weekday_map = {
        0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
    }

    if "month" in df.columns:
        df["month_name"] = df["month"].map(month_map)

    if "weekday" in df.columns:
        df["weekday_name"] = df["weekday"].map(weekday_map)

    if "bars_held" in df.columns:
        bars_bins = [0, 3, 6, 12, 18, 24, 30, 9999]
        bars_labels = ["1-3", "4-6", "7-12", "13-18", "19-24", "25-30", "31+"]
        df["bars_bucket"] = pd.cut(df["bars_held"], bins=bars_bins, labels=bars_labels, right=True)

    if "entry_hour" in df.columns:
        hour_bins = [0, 8, 10, 12, 14, 24]
        hour_labels = ["00-07", "08-09", "10-11", "12-13", "14-23"]
        df["hour_bucket"] = pd.cut(df["entry_hour"], bins=hour_bins, labels=hour_labels, right=False)

    print("\n" + "=" * 80)
    print("ANÁLISIS PROFUNDO DEL BLOQUE MALO P2")
    print("=" * 80)

    print_block("POR MES", build_summary(df, "month_name"), sort_by="month_name", ascending=True)
    print_block("POR HORA DE ENTRADA", build_summary(df, "entry_hour"), sort_by="entry_hour", ascending=True)
    print_block("POR FRANJA HORARIA", build_summary(df, "hour_bucket"), sort_by="hour_bucket", ascending=True)
    print_block("POR DÍA DE LA SEMANA", build_summary(df, "weekday_name"), sort_by="weekday_name", ascending=True)
    print_block("POR DURACIÓN", build_summary(df, "bars_bucket"), sort_by="bars_bucket", ascending=True)

    print_block(
        "TRADES P2",
        df[[
            "entry_time", "exit_time", "side", "entry_hour", "weekday",
            "month", "adx", "atr", "bars_held", "exit_reason", "pnl", "pnl_r"
        ]].sort_values("entry_time", ascending=True)
    )

    print("\n=== PISTAS RÁPIDAS ===")
    month_summary = build_summary(df, "month_name").sort_values("pnl", ascending=False)
    if not month_summary.empty:
        best_month = month_summary.iloc[0]
        worst_month = month_summary.iloc[-1]
        print(
            f"Mejor mes: {best_month['month_name']} | trades={int(best_month['trades'])} "
            f"| pnl={best_month['pnl']:.2f} | pf={best_month['profit_factor']:.3f}"
        )
        print(
            f"Peor mes:  {worst_month['month_name']} | trades={int(worst_month['trades'])} "
            f"| pnl={worst_month['pnl']:.2f} | pf={worst_month['profit_factor']:.3f}"
        )

    hour_summary = build_summary(df, "entry_hour").sort_values("pnl", ascending=False)
    if not hour_summary.empty:
        best_hour = hour_summary.iloc[0]
        worst_hour = hour_summary.iloc[-1]
        print(
            f"Mejor hora: {int(best_hour['entry_hour'])} | trades={int(best_hour['trades'])} "
            f"| pnl={best_hour['pnl']:.2f} | pf={best_hour['profit_factor']:.3f}"
        )
        print(
            f"Peor hora:  {int(worst_hour['entry_hour'])} | trades={int(worst_hour['trades'])} "
            f"| pnl={worst_hour['pnl']:.2f} | pf={worst_hour['profit_factor']:.3f}"
        )

    dur_summary = build_summary(df, "bars_bucket").sort_values("pnl", ascending=False)
    if not dur_summary.empty:
        best_dur = dur_summary.iloc[0]
        worst_dur = dur_summary.iloc[-1]
        print(
            f"Mejor duración: {best_dur['bars_bucket']} | trades={int(best_dur['trades'])} "
            f"| pnl={best_dur['pnl']:.2f} | pf={best_dur['profit_factor']:.3f}"
        )
        print(
            f"Peor duración:  {worst_dur['bars_bucket']} | trades={int(worst_dur['trades'])} "
            f"| pnl={worst_dur['pnl']:.2f} | pf={worst_dur['profit_factor']:.3f}"
        )


if __name__ == "__main__":
    main()