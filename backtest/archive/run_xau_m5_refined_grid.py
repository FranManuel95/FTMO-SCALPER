from itertools import product
import os
import pandas as pd

from backtest.backtester_xau_m5 import XAUM5Backtester


def verdict(row):
    if (
        row["trades"] >= 35
        and row["win_rate"] >= 45.0
        and row["profit_factor"] >= 1.30
        and row["max_dd_pct"] <= 8.0
        and row["expectancy"] > 0
        and row["total_return_pct"] >= 3.0
        and row["second_half_pf"] >= 1.10
    ):
        return "APROBADO"
    return "RECHAZADO"


def score_result(r):
    pf = float(r["profit_factor"]) if r["profit_factor"] != float("inf") else 999.0
    exp = float(r["expectancy"])
    ret = float(r["total_return_pct"])
    dd = float(r["max_dd_pct"])
    trades = float(r["trades"])
    timeout_pct = float(r["timeout_pct"])
    avg_timeout_r = float(r["avg_timeout_r"])
    second_half_pf = float(r["second_half_pf"])

    score = (
        pf * 100.0
        + exp * 2.0
        + ret * 3.0
        - dd * 15.0
        + min(trades, 80) * 0.5
    )

    if trades < 35:
        score -= 40.0
    if timeout_pct > 75.0:
        score -= 20.0
    if avg_timeout_r < 0.05:
        score -= 15.0
    if second_half_pf < 1.10:
        score -= 25.0

    return round(score, 4)


def get_pf_from_trades(df):
    if df.empty:
        return 0.0
    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = abs(df[df["pnl"] < 0]["pnl"].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return round(float(wins / losses), 3)


def analyze_trade_log(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        return {
            "timeout_pct": 0.0,
            "avg_timeout_r": 0.0,
            "second_half_pf": 0.0,
        }

    df = pd.read_csv(csv_path)
    if df.empty:
        return {
            "timeout_pct": 0.0,
            "avg_timeout_r": 0.0,
            "second_half_pf": 0.0,
        }

    timeout_df = df[df["exit_reason"] == "timeout"].copy()
    timeout_pct = round((len(timeout_df) / len(df)) * 100.0, 2) if len(df) else 0.0
    avg_timeout_r = round(float(timeout_df["r_multiple"].mean()), 4) if not timeout_df.empty else 0.0

    df["entry_time"] = pd.to_datetime(df["entry_time"])
    midpoint = df["entry_time"].sort_values().iloc[len(df) // 2]
    second_half = df[df["entry_time"] >= midpoint].copy()
    second_half_pf = get_pf_from_trades(second_half)

    return {
        "timeout_pct": timeout_pct,
        "avg_timeout_r": avg_timeout_r,
        "second_half_pf": second_half_pf,
    }


def run_single_test(
    rr_ratio,
    breakeven_trigger_r,
    max_hold_m5_bars,
    breakout_buffer_atr,
    body_pct_min,
    regime_adx_min,
    min_h1_ema_spread_atr,
    h1_slope_lookback,
):
    bt = XAUM5Backtester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=rr_ratio,
        trade_mode="SELL_ONLY",
    )

    bt.BREAKEVEN_TRIGGER_R = breakeven_trigger_r
    bt.MAX_HOLD_M5_BARS = max_hold_m5_bars
    bt.BREAKOUT_BUFFER_ATR = breakout_buffer_atr
    bt.BODY_PCT_MIN = body_pct_min
    bt.REGIME_ADX_MIN = regime_adx_min
    bt.MIN_H1_EMA_SPREAD_ATR = min_h1_ema_spread_atr
    bt.H1_SLOPE_LOOKBACK = h1_slope_lookback

    run_label = (
        f"rr{str(rr_ratio).replace('.', '')}"
        f"_be{str(breakeven_trigger_r).replace('.', '')}"
        f"_h{max_hold_m5_bars}"
        f"_buf{str(breakout_buffer_atr).replace('.', '')}"
        f"_body{str(body_pct_min).replace('.', '')}"
        f"_adx{regime_adx_min}"
        f"_spr{str(min_h1_ema_spread_atr).replace('.', '')}"
        f"_slp{h1_slope_lookback}"
    )
    bt.run_label = run_label

    result = bt.run()
    diag = getattr(bt, "last_diagnostics", {})
    trades_csv = diag.get("trades_csv")

    extra = analyze_trade_log(trades_csv)

    row = {
        "rr_ratio": rr_ratio,
        "breakeven_trigger_r": breakeven_trigger_r,
        "max_hold_m5_bars": max_hold_m5_bars,
        "breakout_buffer_atr": breakout_buffer_atr,
        "body_pct_min": body_pct_min,
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
        "timeout_pct": extra["timeout_pct"],
        "avg_timeout_r": extra["avg_timeout_r"],
        "second_half_pf": extra["second_half_pf"],
        "trades_csv": trades_csv,
    }

    row["verdict"] = verdict(row)
    row["score"] = score_result(row)
    return row


def main():
    rr_ratio_values = [1.4, 1.5, 1.6]
    breakeven_trigger_r_values = [0.7, 0.8, 0.9]
    max_hold_m5_bars_values = [18, 24]
    breakout_buffer_atr_values = [0.01, 0.02, 0.03]
    body_pct_min_values = [0.15, 0.20, 0.25]
    regime_adx_min_values = [22, 24, 26]
    min_h1_ema_spread_atr_values = [0.15, 0.20, 0.25]
    h1_slope_lookback_values = [2, 3]

    configs = list(product(
        rr_ratio_values,
        breakeven_trigger_r_values,
        max_hold_m5_bars_values,
        breakout_buffer_atr_values,
        body_pct_min_values,
        regime_adx_min_values,
        min_h1_ema_spread_atr_values,
        h1_slope_lookback_values,
    ))

    print(f"\nLanzando refined grid M5 con {len(configs)} combinaciones...\n")

    results = []
    total = len(configs)

    for idx, cfg in enumerate(configs, start=1):
        (
            rr_ratio,
            breakeven_trigger_r,
            max_hold_m5_bars,
            breakout_buffer_atr,
            body_pct_min,
            regime_adx_min,
            min_h1_ema_spread_atr,
            h1_slope_lookback,
        ) = cfg

        print(
            f"[{idx:>4}/{total}] "
            f"RR={rr_ratio} | BE={breakeven_trigger_r} | HOLD={max_hold_m5_bars} | "
            f"BUFFER={breakout_buffer_atr} | BODY={body_pct_min} | "
            f"ADX={regime_adx_min} | SPREAD={min_h1_ema_spread_atr} | "
            f"SLOPE={h1_slope_lookback}"
        )

        row = run_single_test(
            rr_ratio=rr_ratio,
            breakeven_trigger_r=breakeven_trigger_r,
            max_hold_m5_bars=max_hold_m5_bars,
            breakout_buffer_atr=breakout_buffer_atr,
            body_pct_min=body_pct_min,
            regime_adx_min=regime_adx_min,
            min_h1_ema_spread_atr=min_h1_ema_spread_atr,
            h1_slope_lookback=h1_slope_lookback,
        )
        results.append(row)

    results.sort(key=lambda x: x["score"], reverse=True)

    os.makedirs("backtest/results", exist_ok=True)
    out_csv = "backtest/results/xau_m5_refined_grid_results.csv"
    pd.DataFrame(results).to_csv(out_csv, index=False)

    print("\n" + "=" * 220)
    print("TOP 20 RESULTADOS - REFINED GRID XAUUSD M5 SELL_ONLY")
    print("=" * 220)
    print(
        f"{'RANK':<6}"
        f"{'RR':>6}"
        f"{'BE':>6}"
        f"{'HOLD':>8}"
        f"{'BUF':>8}"
        f"{'BODY':>8}"
        f"{'ADX':>8}"
        f"{'SPR':>8}"
        f"{'SLP':>6}"
        f"{'TRD':>6}"
        f"{'WR%':>8}"
        f"{'PF':>8}"
        f"{'DD%':>8}"
        f"{'RET%':>8}"
        f"{'EXP':>10}"
        f"{'TO%':>8}"
        f"{'TO_R':>8}"
        f"{'2H_PF':>8}"
        f"{'SCORE':>10}"
        f"{'VEREDICTO':>14}"
    )
    print("-" * 220)

    for i, r in enumerate(results[:20], start=1):
        print(
            f"{i:<6}"
            f"{r['rr_ratio']:>6.2f}"
            f"{r['breakeven_trigger_r']:>6.2f}"
            f"{r['max_hold_m5_bars']:>8}"
            f"{r['breakout_buffer_atr']:>8.2f}"
            f"{r['body_pct_min']:>8.2f}"
            f"{r['regime_adx_min']:>8}"
            f"{r['min_h1_ema_spread_atr']:>8.2f}"
            f"{r['h1_slope_lookback']:>6}"
            f"{r['trades']:>6}"
            f"{r['win_rate']:>8.2f}"
            f"{r['profit_factor']:>8}"
            f"{r['max_dd_pct']:>8.2f}"
            f"{r['total_return_pct']:>8.2f}"
            f"{r['expectancy']:>10.2f}"
            f"{r['timeout_pct']:>8.2f}"
            f"{r['avg_timeout_r']:>8.4f}"
            f"{r['second_half_pf']:>8}"
            f"{r['score']:>10.2f}"
            f"{r['verdict']:>14}"
        )

    print("-" * 220)
    print(f"\nResultados guardados en: {out_csv}")

    approved = [r for r in results if r["verdict"] == "APROBADO"]
    print(f"Aprobadas: {len(approved)} / {len(results)}")

    if approved:
        print("\nMejor aprobada:")
        print(approved[0])
    else:
        print("\nNo hubo combinaciones aprobadas con estos filtros.")


if __name__ == "__main__":
    main()