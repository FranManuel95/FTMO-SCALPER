import os
import pandas as pd

from backtest.backtester_gbp import GBPBacktester


def run_combo(
    trade_mode: str,
    session_start: int,
    session_end: int,
    adx_min: float,
    adx_max: float,
):
    bt = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.4,
        symbol="GBPUSD",
        export_trades=False,
        session_start=session_start,
        session_end=session_end,
        adx_min=adx_min,
        adx_max=adx_max,
        trade_mode=trade_mode,
    )

    result = bt.run()

    return {
        "mode": trade_mode,
        "session_start": session_start,
        "session_end": session_end,
        "adx_min": adx_min,
        "adx_max": adx_max,
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
    modes = ["BOTH", "SELL_ONLY", "BUY_ONLY"]
    session_starts = [8]
    session_ends = [14, 15]
    adx_mins = [25, 30]
    adx_maxs = [40, 45]

    valid_combos = [
        (mode, session_start, session_end, adx_min, adx_max)
        for mode in modes
        for session_start in session_starts
        for session_end in session_ends
        for adx_min in adx_mins
        for adx_max in adx_maxs
        if adx_min < adx_max
    ]

    total = len(valid_combos)
    results = []

    print(f"Lanzando grid GBPUSD pequeño con {total} combinaciones...\n")

    for idx, (mode, session_start, session_end, adx_min, adx_max) in enumerate(valid_combos, start=1):
        print(
            f"[{idx:>2}/{total}] "
            f"MODE={mode} | "
            f"SESSION={session_start}-{session_end} | "
            f"ADX={adx_min}-{adx_max}"
        )

        try:
            row = run_combo(
                trade_mode=mode,
                session_start=session_start,
                session_end=session_end,
                adx_min=adx_min,
                adx_max=adx_max,
            )
            results.append(row)

        except Exception as e:
            print(f"   ERROR: {e}")

    if not results:
        raise ValueError("No hubo resultados válidos.")

    df = pd.DataFrame(results)

    df = df.sort_values(
        by=["profit_factor", "total_return_pct", "expectancy", "max_dd_pct"],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)

    os.makedirs("backtest/results", exist_ok=True)
    out_path = "backtest/results/gbpusd_small_grid_results.csv"
    df.to_csv(out_path, index=False)

    print("\n=== TOP 10 COMBINACIONES ===")
    print(df.head(10).to_string(index=False))

    print(f"\nResultados guardados en: {out_path}")


if __name__ == "__main__":
    main()