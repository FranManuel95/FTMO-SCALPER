# backtest/run_xau_m5_validation.py

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


def run_period(name, start_date=None, end_date=None):
    bt = XAUM5Backtester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.5,
        trade_mode="SELL_ONLY",
        start_date=start_date,
        end_date=end_date,
    )

    bt.BREAKEVEN_TRIGGER_R = 1.0
    bt.MAX_HOLD_M5_BARS = 24

    bt.REGIME_ADX_MIN = 22
    bt.MIN_H1_EMA_SPREAD_ATR = 0.15
    bt.H1_SLOPE_LOOKBACK = 3

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})

    return {
        "name": name,
        "start": str(start_date) if start_date is not None else "-",
        "end": str(end_date) if end_date is not None else "-",
        "trades": result.total_trades,
        "wr": round(result.win_rate * 100, 2),
        "pf": result.profit_factor,
        "sharpe": result.sharpe_ratio,
        "sortino": result.sortino_ratio,
        "dd": round(result.max_drawdown * 100, 2),
        "ret": round(result.total_return * 100, 2),
        "exp": result.expectancy,
        "verdict": verdict(result),
        "diag": diag,
    }


def load_full_index():
    bt = XAUM5Backtester()
    df = bt._read_ohlc_csv(bt.DATA_PATH_M5)
    return df.index


def print_results_table(rows):
    print("\n" + "=" * 150)
    print("VALIDACIÓN TEMPORAL XAUUSD M5 SELL_ONLY")
    print("=" * 150)

    header = (
        f"{'NOMBRE':<18}"
        f"{'START':<22}"
        f"{'END':<22}"
        f"{'TRADES':>8}"
        f"{'WR%':>8}"
        f"{'PF':>8}"
        f"{'SHARPE':>10}"
        f"{'SORTINO':>10}"
        f"{'DD%':>8}"
        f"{'RET%':>8}"
        f"{'EXP':>10}"
        f"{'VEREDICTO':>14}"
    )
    print(header)
    print("-" * 150)

    for r in rows:
        print(
            f"{r['name']:<18}"
            f"{r['start']:<22}"
            f"{r['end']:<22}"
            f"{r['trades']:>8}"
            f"{r['wr']:>8.2f}"
            f"{r['pf']:>8}"
            f"{r['sharpe']:>10}"
            f"{r['sortino']:>10}"
            f"{r['dd']:>8.2f}"
            f"{r['ret']:>8.2f}"
            f"{r['exp']:>10.2f}"
            f"{r['verdict']:>14}"
        )

    print("-" * 150)


def print_diagnostics(rows):
    print("\n" + "=" * 120)
    print("DIAGNÓSTICOS POR BLOQUE")
    print("=" * 120)

    for r in rows:
        diag = r["diag"]
        print(
            f"\n[{r['name']}] Trades={r['trades']} | PF={r['pf']} | WR={r['wr']}% | RET={r['ret']}%"
        )
        print(f"  Exit reasons: {diag.get('exit_reason_counter', {})}")
        print(f"  Break-even activado: {diag.get('be_activated_count', 0)} veces")
        print(f"  Sell stats: {diag.get('sell_stats', {})}")


def main():
    idx = load_full_index()
    idx = pd.DatetimeIndex(idx).sort_values()

    start = idx[0]
    end = idx[-1]
    split = idx[len(idx) // 2]

    rows = []

    rows.append(run_period("FULL", start_date=start, end_date=end))
    rows.append(run_period("FIRST_HALF", start_date=start, end_date=split))
    rows.append(run_period("SECOND_HALF", start_date=split + pd.Timedelta(minutes=5), end_date=end))

    unique_months = pd.Series(idx).dt.to_period("M").drop_duplicates().tolist()

    for period in unique_months:
        month_start = pd.Timestamp(period.start_time)
        month_end = pd.Timestamp(period.end_time)
        name = f"MONTH_{period}"
        try:
            rows.append(run_period(name, start_date=month_start, end_date=month_end))
        except Exception as e:
            print(f"Saltando {name}: {e}")

    print_results_table(rows)
    print_diagnostics(rows)


if __name__ == "__main__":
    main()