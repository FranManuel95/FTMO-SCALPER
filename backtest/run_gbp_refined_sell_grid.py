import os
import pandas as pd

from backtest.backtester_gbp import GBPBacktester


def run_combo(
    adx_min: float,
    adx_max: float,
    rr_ratio: float,
    atr_sl_mult: float,
):
    bt = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=rr_ratio,
        atr_sl_mult=atr_sl_mult,
        symbol="GBPUSD",
        export_trades=False,
        session_start=8,
        session_end=14,
        adx_min=adx_min,
        adx_max=adx_max,
        trade_mode="SELL_ONLY",
    )

    result = bt.run()

    return {
        "mode": "SELL_ONLY",
        "session_start": 8,
        "session_end": 14,
        "adx_min": adx_min,
        "adx_max": adx_max,
        "rr_ratio": rr_ratio,
        "atr_sl_mult": atr_sl_mult,
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
    }


def main():
    adx_mins = [28, 30, 32]
    adx_maxs = [38, 40, 42]
    rr_ratios = [1.2, 1.4, 1.6]
    atr_sl_mults = [1.0, 1.2, 1.4]

    valid_combos = [
        (adx_min, adx_max, rr_ratio, atr_sl_mult)
        for adx_min in adx_mins
        for adx_max in adx_maxs
        for rr_ratio in rr_ratios
        for atr_sl_mult in atr_sl_mults
        if adx_min < adx_max
    ]

    total = len(valid_combos)
    results = []

    print(f"Lanzando grid refinado GBPUSD SELL con {total} combinaciones...\n")

    for idx, (adx_min, adx_max, rr_ratio, atr_sl_mult) in enumerate(valid_combos, start=1):
        print(
            f"[{idx:>2}/{total}] "
            f"MODE=SELL_ONLY | SESSION=8-14 | "
            f"ADX={adx_min}-{adx_max} | "
            f"RR={rr_ratio} | SLxATR={atr_sl_mult}"
        )

        try:
            row = run_combo(
                adx_min=adx_min,
                adx_max=adx_max,
                rr_ratio=rr_ratio,
                atr_sl_mult=atr_sl_mult,
            )
            results.append(row)
        except Exception as e:
            print(f"   ERROR: {e}")

    if not results:
        raise ValueError("No hubo resultados válidos.")

    df = pd.DataFrame(results)

    df = df.sort_values(
        by=["profit_factor", "total_return_pct", "expectancy", "max_dd_pct", "trades"],
        ascending=[False, False, False, True, False]
    ).reset_index(drop=True)

    os.makedirs("backtest/results", exist_ok=True)
    out_path = "backtest/results/gbpusd_refined_sell_grid_results.csv"
    df.to_csv(out_path, index=False)

    print("\n=== TOP 15 COMBINACIONES ===")
    print(df.head(15).to_string(index=False))

    print(f"\nResultados guardados en: {out_path}")


if __name__ == "__main__":
    main()