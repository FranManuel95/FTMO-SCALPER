import pandas as pd

from backtest.backtester_xau_m5 import XAUM5Backtester


def verdict(result):
    if (
        result.win_rate >= 0.45
        and result.profit_factor >= 1.3
        and result.sharpe_ratio >= 1.5
        and result.max_drawdown <= 0.08
    ):
        return "APROBADO"
    return "RECHAZADO"


def run_block(name, start_date=None, end_date=None):
    bt = XAUM5Backtester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.5,
        trade_mode="SELL_ONLY",
        start_date=start_date,
        end_date=end_date,
    )

    bt.BREAKEVEN_TRIGGER_R = 0.8
    bt.MAX_HOLD_M5_BARS = 24
    bt.BREAKOUT_BUFFER_ATR = 0.01
    bt.BODY_PCT_MIN = 0.15
    bt.REGIME_ADX_MIN = 22
    bt.MIN_H1_EMA_SPREAD_ATR = 0.20
    bt.H1_SLOPE_LOOKBACK = 3
    bt.run_label = f"validation_{name.lower()}"

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})

    row = {
        "name": name,
        "trades": result.total_trades,
        "win_rate": round(result.win_rate * 100, 2),
        "profit_factor": result.profit_factor,
        "sharpe": result.sharpe_ratio,
        "sortino": result.sortino_ratio,
        "max_dd_pct": round(result.max_drawdown * 100, 2),
        "total_return_pct": round(result.total_return * 100, 2),
        "expectancy": result.expectancy,
        "verdict": verdict(result),
        "start_date": start_date,
        "end_date": end_date,
        "diag": diag,
    }
    return row


def main():
    ranges = [
        ("FULL", "2024-11-01", "2026-04-09"),
        ("FIRST_HALF", "2024-11-01", "2025-07-22"),
        ("SECOND_HALF", "2025-07-22", "2026-04-09"),
        ("MONTH_2024-11", "2024-11-01", "2024-11-30"),
        ("MONTH_2024-12", "2024-12-01", "2024-12-31"),
        ("MONTH_2025-01", "2025-01-01", "2025-01-31"),
        ("MONTH_2025-02", "2025-02-01", "2025-02-28"),
        ("MONTH_2025-03", "2025-03-01", "2025-03-31"),
        ("MONTH_2025-04", "2025-04-01", "2025-04-30"),
        ("MONTH_2025-05", "2025-05-01", "2025-05-31"),
        ("MONTH_2025-06", "2025-06-01", "2025-06-30"),
        ("MONTH_2025-07", "2025-07-01", "2025-07-31"),
        ("MONTH_2025-08", "2025-08-01", "2025-08-31"),
        ("MONTH_2025-09", "2025-09-01", "2025-09-30"),
        ("MONTH_2025-10", "2025-10-01", "2025-10-31"),
        ("MONTH_2025-11", "2025-11-01", "2025-11-30"),
        ("MONTH_2025-12", "2025-12-01", "2025-12-31"),
        ("MONTH_2026-01", "2026-01-01", "2026-01-31"),
        ("MONTH_2026-02", "2026-02-01", "2026-02-28"),
        ("MONTH_2026-03", "2026-03-01", "2026-03-31"),
        ("MONTH_2026-04", "2026-04-01", "2026-04-30"),
    ]

    rows = []
    print("\n" + "=" * 150)
    print("VALIDACIÓN TEMPORAL XAUUSD M5 SELL_ONLY - BEST SETUP")
    print("=" * 150)

    print(
        f"{'NOMBRE':<18}"
        f"{'TRADES':>8}"
        f"{'WR%':>8}"
        f"{'PF':>8}"
        f"{'SHARPE':>10}"
        f"{'SORTINO':>10}"
        f"{'DD%':>8}"
        f"{'RET%':>8}"
        f"{'EXPECT':>10}"
        f"{'VEREDICTO':>14}"
    )
    print("-" * 150)

    for name, start_date, end_date in ranges:
        row = run_block(name, start_date, end_date)
        rows.append(row)

        print(
            f"{row['name']:<18}"
            f"{row['trades']:>8}"
            f"{row['win_rate']:>8.2f}"
            f"{row['profit_factor']:>8}"
            f"{row['sharpe']:>10}"
            f"{row['sortino']:>10}"
            f"{row['max_dd_pct']:>8.2f}"
            f"{row['total_return_pct']:>8.2f}"
            f"{row['expectancy']:>10.2f}"
            f"{row['verdict']:>14}"
        )

    print("-" * 150)
    print("\n" + "=" * 120)
    print("DIAGNÓSTICOS POR BLOQUE")
    print("=" * 120)

    for row in rows:
        diag = row["diag"]
        print(
            f"\n[{row['name']}] Trades={row['trades']} | PF={row['profit_factor']} | "
            f"WR={row['win_rate']}% | RET={row['total_return_pct']}%"
        )
        print(f"  Exit reasons: {diag.get('exit_reason_counter', {})}")
        print(f"  Break-even activado: {diag.get('be_activated_count', 0)} veces")
        print(f"  Sell stats: {diag.get('sell_stats', {})}")


if __name__ == "__main__":
    main()