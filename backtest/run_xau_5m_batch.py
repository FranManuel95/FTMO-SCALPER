# backtest/run_xau_m5_batch.py

from itertools import product

from backtest.backtester_xau_m5 import XAUM5Backtester


def score_result(r):
    pf = float(r["profit_factor"]) if r["profit_factor"] != float("inf") else 999.0
    exp = float(r["expectancy"])
    ret = float(r["total_return_pct"])
    dd_penalty = float(r["max_dd_pct"]) * 0.25
    return (pf * 100.0) + (exp * 2.0) + ret - dd_penalty


def run_single_test(regime_adx_min, min_h1_ema_spread_atr, h1_slope_lookback):
    bt = XAUM5Backtester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.5,
        trade_mode="SELL_ONLY",
    )

    bt.BREAKEVEN_TRIGGER_R = 1.0
    bt.MAX_HOLD_M5_BARS = 24
    bt.REGIME_ADX_MIN = regime_adx_min
    bt.MIN_H1_EMA_SPREAD_ATR = min_h1_ema_spread_atr
    bt.H1_SLOPE_LOOKBACK = h1_slope_lookback

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})

    row = {
        "regime_adx_min": regime_adx_min,
        "min_h1_ema_spread_atr": min_h1_ema_spread_atr,
        "h1_slope_lookback": h1_slope_lookback,
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
    }
    row["score"] = round(score_result(row), 4)
    return row


def main():
    regime_adx_min_values = [22, 24, 26]
    min_h1_ema_spread_atr_values = [0.15, 0.20, 0.25]
    h1_slope_lookback_values = [2, 3]

    configs = list(product(
        regime_adx_min_values,
        min_h1_ema_spread_atr_values,
        h1_slope_lookback_values,
    ))

    results = []

    print(f"\nLanzando grid M5 con {len(configs)} combinaciones...\n")

    for idx, (adx_min, spread, slope) in enumerate(configs, start=1):
        print(
            f"[{idx:>2}/{len(configs)}] ADX={adx_min} | SPREAD={spread} | SLOPE={slope}"
        )
        results.append(run_single_test(adx_min, spread, slope))

    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 150)
    print("TOP RESULTADOS M5")
    print("=" * 150)
    print(
        f"{'RANK':<6}{'ADX':>8}{'SPREAD':>10}{'SLOPE':>8}{'TRADES':>8}{'WR%':>8}"
        f"{'PF':>8}{'DD%':>8}{'RET%':>8}{'EXPECT':>10}{'SCORE':>10}"
    )
    print("-" * 150)

    for i, r in enumerate(results, start=1):
        print(
            f"{i:<6}{r['regime_adx_min']:>8}{r['min_h1_ema_spread_atr']:>10.2f}"
            f"{r['h1_slope_lookback']:>8}{r['trades']:>8}{r['win_rate']:>8.2f}"
            f"{r['profit_factor']:>8}{r['max_dd_pct']:>8.2f}{r['total_return_pct']:>8.2f}"
            f"{r['expectancy']:>10.2f}{r['score']:>10.2f}"
        )

    best = results[0]
    print("\nMejor combinación M5:")
    print(best)


if __name__ == "__main__":
    main()