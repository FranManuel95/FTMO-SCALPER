# backtest/run_xau_batch.py

from itertools import product

from backtest.backtester_xau import XAUBacktester


def verdict(result):
    if (
        result.win_rate >= 0.45
        and result.profit_factor >= 1.3
        and result.sharpe_ratio >= 1.5
        and result.max_drawdown <= 0.08
    ):
        return "APROBADO"
    return "RECHAZADO"


def score_result(r):
    """
    Score orientado a robustez:
    - prioriza PF
    - luego expectancy
    - luego retorno
    - penaliza drawdown
    """
    pf = float(r["profit_factor"]) if r["profit_factor"] != float("inf") else 999.0
    exp = float(r["expectancy"])
    ret = float(r["total_return_pct"])
    dd_penalty = float(r["max_dd_pct"]) * 0.25

    return (pf * 100.0) + (exp * 2.0) + ret - dd_penalty


def run_single_test(
    trade_mode,
    rr_ratio,
    breakeven_trigger_r,
    max_hold_m5_bars,
    regime_adx_min,
    min_h1_ema_spread_atr,
    h1_slope_lookback,
):
    bt = XAUBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=rr_ratio,
        trade_mode=trade_mode,
    )

    # Base fija
    bt.BREAKEVEN_TRIGGER_R = breakeven_trigger_r
    bt.MAX_HOLD_M5_BARS = max_hold_m5_bars

    # Grid del filtro de régimen
    bt.REGIME_ADX_MIN = regime_adx_min
    bt.MIN_H1_EMA_SPREAD_ATR = min_h1_ema_spread_atr
    bt.H1_SLOPE_LOOKBACK = h1_slope_lookback

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})

    row = {
        "mode": trade_mode,
        "rr": rr_ratio,
        "be": breakeven_trigger_r,
        "hold": max_hold_m5_bars,
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
        "verdict": verdict(result),

        # Diagnóstico
        "exit_reason_counter": diag.get("exit_reason_counter", {}),
        "side_counter": diag.get("side_counter", {}),
        "be_activated_count": diag.get("be_activated_count", 0),
        "be_activation_rate_pct": diag.get("be_activation_rate_pct", 0.0),
        "buy_stats": diag.get("buy_stats", {}),
        "sell_stats": diag.get("sell_stats", {}),
        "regime_filter": diag.get("regime_filter", {}),
    }

    row["score"] = round(score_result(row), 4)
    return row


def print_top_results(results, top_n=18):
    print("\n" + "=" * 220)
    print(f"TOP {top_n} RESULTADOS - GRID SEARCH FILTRO DE RÉGIMEN XAUUSD SELL_ONLY")
    print("=" * 220)

    header = (
        f"{'RANK':<6}"
        f"{'MODE':<12}"
        f"{'RR':>6}"
        f"{'BE':>8}"
        f"{'HOLD':>8}"
        f"{'ADX':>8}"
        f"{'SPREAD':>10}"
        f"{'SLOPE':>8}"
        f"{'TRADES':>8}"
        f"{'WR%':>8}"
        f"{'PF':>8}"
        f"{'SHARPE':>10}"
        f"{'SORTINO':>10}"
        f"{'MAXDD%':>10}"
        f"{'RET%':>10}"
        f"{'AVG WIN':>12}"
        f"{'AVG LOSS':>12}"
        f"{'EXPECT':>10}"
        f"{'SCORE':>10}"
        f"{'VEREDICTO':>14}"
    )
    print(header)
    print("-" * 220)

    for i, r in enumerate(results[:top_n], start=1):
        print(
            f"{i:<6}"
            f"{r['mode']:<12}"
            f"{r['rr']:>6.2f}"
            f"{r['be']:>8.2f}"
            f"{r['hold']:>8}"
            f"{r['regime_adx_min']:>8}"
            f"{r['min_h1_ema_spread_atr']:>10.2f}"
            f"{r['h1_slope_lookback']:>8}"
            f"{r['trades']:>8}"
            f"{r['win_rate']:>8.2f}"
            f"{r['profit_factor']:>8}"
            f"{r['sharpe']:>10}"
            f"{r['sortino']:>10}"
            f"{r['max_dd_pct']:>10.2f}"
            f"{r['total_return_pct']:>10.2f}"
            f"{r['avg_win']:>12.2f}"
            f"{r['avg_loss']:>12.2f}"
            f"{r['expectancy']:>10.2f}"
            f"{r['score']:>10.2f}"
            f"{r['verdict']:>14}"
        )

    print("-" * 220)


def print_best_by_metric(results):
    best_pf = max(results, key=lambda x: x["profit_factor"])
    best_exp = max(results, key=lambda x: x["expectancy"])
    best_ret = max(results, key=lambda x: x["total_return_pct"])
    best_score = max(results, key=lambda x: x["score"])

    print("\nMEJORES POR MÉTRICA")
    print("-" * 120)
    print(
        f"Mejor PF       -> MODE={best_pf['mode']} | RR={best_pf['rr']} | HOLD={best_pf['hold']} | "
        f"ADX={best_pf['regime_adx_min']} | SPREAD={best_pf['min_h1_ema_spread_atr']} | "
        f"SLOPE={best_pf['h1_slope_lookback']} | PF={best_pf['profit_factor']} | "
        f"WR={best_pf['win_rate']}% | RET={best_pf['total_return_pct']}%"
    )
    print(
        f"Mejor Expect.  -> MODE={best_exp['mode']} | RR={best_exp['rr']} | HOLD={best_exp['hold']} | "
        f"ADX={best_exp['regime_adx_min']} | SPREAD={best_exp['min_h1_ema_spread_atr']} | "
        f"SLOPE={best_exp['h1_slope_lookback']} | EXP={best_exp['expectancy']} | "
        f"PF={best_exp['profit_factor']} | RET={best_exp['total_return_pct']}%"
    )
    print(
        f"Mejor Retorno  -> MODE={best_ret['mode']} | RR={best_ret['rr']} | HOLD={best_ret['hold']} | "
        f"ADX={best_ret['regime_adx_min']} | SPREAD={best_ret['min_h1_ema_spread_atr']} | "
        f"SLOPE={best_ret['h1_slope_lookback']} | RET={best_ret['total_return_pct']}% | "
        f"PF={best_ret['profit_factor']} | WR={best_ret['win_rate']}%"
    )
    print(
        f"Mejor Score    -> MODE={best_score['mode']} | RR={best_score['rr']} | HOLD={best_score['hold']} | "
        f"ADX={best_score['regime_adx_min']} | SPREAD={best_score['min_h1_ema_spread_atr']} | "
        f"SLOPE={best_score['h1_slope_lookback']} | SCORE={best_score['score']} | "
        f"PF={best_score['profit_factor']} | RET={best_score['total_return_pct']}%"
    )
    print("-" * 120)


def print_approved(results):
    approved = [r for r in results if r["verdict"] == "APROBADO"]

    print("\nRESULTADOS APROBADOS")
    print("-" * 120)
    if not approved:
        print("Ninguna combinación cumple todos los filtros actuales.")
        return

    for r in approved:
        print(
            f"MODE={r['mode']} | RR={r['rr']} | HOLD={r['hold']} | "
            f"ADX={r['regime_adx_min']} | SPREAD={r['min_h1_ema_spread_atr']} | "
            f"SLOPE={r['h1_slope_lookback']} | Trades={r['trades']} | "
            f"WR={r['win_rate']}% | PF={r['profit_factor']} | DD={r['max_dd_pct']}% | "
            f"Ret={r['total_return_pct']}%"
        )


def print_diagnostics_of_best(results):
    if not results:
        return

    best = results[0]

    print("\n" + "=" * 130)
    print("DIAGNÓSTICO DEL MEJOR RESULTADO")
    print("=" * 130)
    print(
        f"MODE={best['mode']} | RR={best['rr']} | BE={best['be']} | HOLD={best['hold']} | "
        f"ADX={best['regime_adx_min']} | SPREAD={best['min_h1_ema_spread_atr']} | "
        f"SLOPE={best['h1_slope_lookback']} | Trades={best['trades']} | "
        f"PF={best['profit_factor']} | WR={best['win_rate']}% | RET={best['total_return_pct']}%"
    )

    print("\nExit reasons:")
    for k, v in best.get("exit_reason_counter", {}).items():
        print(f"  - {k}: {v}")

    print("\nSides:")
    for k, v in best.get("side_counter", {}).items():
        print(f"  - {k}: {v}")

    print(
        f"\nBreak-even activado: {best.get('be_activated_count', 0)} veces "
        f"({best.get('be_activation_rate_pct', 0.0)}%)"
    )

    buy = best.get("buy_stats", {})
    sell = best.get("sell_stats", {})

    print("\nBUY stats:")
    print(
        f"  Trades={buy.get('trades', 0)} | "
        f"WR={buy.get('win_rate_pct', 0.0)}% | "
        f"PF={buy.get('profit_factor', 0.0)} | "
        f"Expectancy={buy.get('expectancy', 0.0)}"
    )

    print("\nSELL stats:")
    print(
        f"  Trades={sell.get('trades', 0)} | "
        f"WR={sell.get('win_rate_pct', 0.0)}% | "
        f"PF={sell.get('profit_factor', 0.0)} | "
        f"Expectancy={sell.get('expectancy', 0.0)}"
    )

    print("\nRegime filter:")
    print(best.get("regime_filter", {}))


def main():
    # Base fija del sistema
    trade_modes = ["SELL_ONLY"]
    rr_values = [1.5]
    be_values = [1.0]
    hold_values = [24]

    # Grid del filtro de régimen
    regime_adx_min_values = [22, 24, 26]
    min_h1_ema_spread_atr_values = [0.15, 0.20, 0.25]
    h1_slope_lookback_values = [2, 3]

    configs = list(product(
        trade_modes,
        rr_values,
        be_values,
        hold_values,
        regime_adx_min_values,
        min_h1_ema_spread_atr_values,
        h1_slope_lookback_values,
    ))

    results = []
    total = len(configs)

    print(f"\nLanzando grid search del filtro de régimen con {total} combinaciones...\n")

    for idx, (mode, rr, be, hold, adx_min, spread, slope_lb) in enumerate(configs, start=1):
        print(
            f"[{idx:>2}/{total}] Ejecutando MODE={mode} | RR={rr} | BE={be}R | HOLD={hold} | "
            f"ADX={adx_min} | SPREAD={spread} | SLOPE={slope_lb}"
        )

        row = run_single_test(
            trade_mode=mode,
            rr_ratio=rr,
            breakeven_trigger_r=be,
            max_hold_m5_bars=hold,
            regime_adx_min=adx_min,
            min_h1_ema_spread_atr=min_h1_ema_spread_atr_values[
                min_h1_ema_spread_atr_values.index(spread)
            ],
            h1_slope_lookback=slope_lb,
        )
        results.append(row)

    results.sort(key=lambda x: x["score"], reverse=True)

    print_top_results(results, top_n=len(results))
    print_best_by_metric(results)
    print_approved(results)
    print_diagnostics_of_best(results)


if __name__ == "__main__":
    main()