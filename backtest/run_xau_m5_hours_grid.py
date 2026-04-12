import os
import pandas as pd

from backtest.backtester_xau_m5 import XAUM5Backtester


def verdict(result):
    if (
        result.win_rate >= 0.45
        and result.profit_factor >= 1.30
        and result.max_drawdown <= 0.08
        and result.total_trades >= 20
    ):
        return "APROBADO"
    return "RECHAZADO"


def score_result(row):
    pf = float(row["profit_factor"]) if row["profit_factor"] != float("inf") else 999.0
    exp = float(row["expectancy"])
    ret = float(row["total_return_pct"])
    dd = float(row["max_dd_pct"])
    trades = float(row["trades"])

    score = (
        pf * 100.0
        + exp * 2.0
        + ret * 3.0
        - dd * 15.0
        + min(trades, 80) * 0.5
    )

    if trades < 20:
        score -= 30.0

    return round(score, 4)


def run_single_test(hours_set, label):
    bt = XAUM5Backtester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.5,
        trade_mode="SELL_ONLY",
    )

    # Mejor setup actual
    bt.BREAKEVEN_TRIGGER_R = 0.8
    bt.MAX_HOLD_M5_BARS = 24
    bt.BREAKOUT_BUFFER_ATR = 0.01
    bt.BODY_PCT_MIN = 0.15
    bt.REGIME_ADX_MIN = 22
    bt.MIN_H1_EMA_SPREAD_ATR = 0.20
    bt.H1_SLOPE_LOOKBACK = 3

    bt.ALLOWED_ENTRY_HOURS = hours_set
    bt.run_label = f"hours_{label}"

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})

    row = {
        "hours_label": label,
        "hours_set": sorted(list(hours_set)),
        "trades": result.total_trades,
        "win_rate": round(result.win_rate * 100, 2),
        "profit_factor": result.profit_factor,
        "sharpe": result.sharpe_ratio,
        "sortino": result.sortino_ratio,
        "max_dd_pct": round(result.max_drawdown * 100, 2),
        "total_return_pct": round(result.total_return * 100, 2),
        "avg_win": result.avg_win,
        "avg_loss": result.avg_loss,
        "expectancy": result.expectancy,
        "exit_reason_counter": diag.get("exit_reason_counter", {}),
        "sell_stats": diag.get("sell_stats", {}),
        "trades_csv": diag.get("trades_csv"),
    }

    row["verdict"] = verdict(result)
    row["score"] = score_result(row)
    return row


def main():
    configs = [
        ({9, 13, 15}, "9_13_15"),
        ({13, 15}, "13_15"),
        ({9, 15}, "9_15"),
        ({9, 13}, "9_13"),
        ({15}, "15"),
        ({13}, "13"),
        ({9}, "9"),
    ]

    results = []

    print("\n" + "=" * 140)
    print("GRID PEQUEÑO DE HORAS - XAUUSD M5 SELL_ONLY")
    print("=" * 140)

    for idx, (hours_set, label) in enumerate(configs, start=1):
        print(f"[{idx}/{len(configs)}] Horas={sorted(list(hours_set))}")
        row = run_single_test(hours_set, label)
        results.append(row)

    results.sort(key=lambda x: x["score"], reverse=True)

    os.makedirs("backtest/results", exist_ok=True)
    out_csv = "backtest/results/xau_m5_hours_grid_results.csv"
    pd.DataFrame(results).to_csv(out_csv, index=False)

    print("\n" + "=" * 170)
    print("RESULTADOS GRID HORAS")
    print("=" * 170)
    print(
        f"{'RANK':<6}"
        f"{'HORAS':<16}"
        f"{'TRADES':>8}"
        f"{'WR%':>8}"
        f"{'PF':>8}"
        f"{'SHARPE':>10}"
        f"{'SORTINO':>10}"
        f"{'DD%':>8}"
        f"{'RET%':>8}"
        f"{'EXPECT':>10}"
        f"{'SCORE':>10}"
        f"{'VEREDICTO':>14}"
    )
    print("-" * 170)

    for i, r in enumerate(results, start=1):
        print(
            f"{i:<6}"
            f"{r['hours_label']:<16}"
            f"{r['trades']:>8}"
            f"{r['win_rate']:>8.2f}"
            f"{r['profit_factor']:>8}"
            f"{r['sharpe']:>10}"
            f"{r['sortino']:>10}"
            f"{r['max_dd_pct']:>8.2f}"
            f"{r['total_return_pct']:>8.2f}"
            f"{r['expectancy']:>10.2f}"
            f"{r['score']:>10.2f}"
            f"{r['verdict']:>14}"
        )

    print("-" * 170)
    print(f"\nResultados guardados en: {out_csv}")

    print("\nMejor combinación:")
    print(results[0])


if __name__ == "__main__":
    main()