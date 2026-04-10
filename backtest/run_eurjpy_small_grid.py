# backtest/run_eurjpy_small_grid.py

from itertools import product
from backtest.backtester_eurjpy import EURJPYBacktester


def main():
    session_windows = [(7, 11), (7, 12), (8, 12)]
    adx_ranges = [(18, 45), (20, 50), (22, 50)]
    rr_ratios = [1.3, 1.4, 1.6]
    atr_sl_mults = [1.0, 1.2, 1.4]
    breakout_buffers = [0.05, 0.10, 0.15]
    body_ratios = [0.45, 0.55, 0.65]

    combos = list(product(
        session_windows,
        adx_ranges,
        rr_ratios,
        atr_sl_mults,
        breakout_buffers,
        body_ratios,
    ))

    print(f"Lanzando grid EURJPY pequeño con {len(combos)} combinaciones...\n")

    best = []

    for idx, (
        session_window,
        adx_range,
        rr_ratio,
        atr_sl_mult,
        breakout_buffer,
        body_ratio,
    ) in enumerate(combos, start=1):
        session_start, session_end = session_window
        adx_min, adx_max = adx_range

        print(
            f"[{idx:>3}/{len(combos)}] "
            f"SESSION={session_start}-{session_end} | "
            f"ADX={adx_min}-{adx_max} | "
            f"RR={rr_ratio} | "
            f"SLxATR={atr_sl_mult} | "
            f"BUFFER_ATR={breakout_buffer} | "
            f"BODY={body_ratio}"
        )

        try:
            bt = EURJPYBacktester(
                symbol="EURJPY",
                export_trades=False,
                session_start=session_start,
                session_end=session_end,
                adx_min=adx_min,
                adx_max=adx_max,
                rr_ratio=rr_ratio,
                atr_sl_mult=atr_sl_mult,
                breakout_buffer_atr=breakout_buffer,
                min_body_ratio=body_ratio,
                risk_per_trade=0.005,
                atr_min=0.10,
                range_atr_min=0.8,
                range_atr_cap=3.5,
                trade_mode="BOTH",
            )
            result = bt.run()

            row = {
                "session": f"{session_start}-{session_end}",
                "adx": f"{adx_min}-{adx_max}",
                "rr_ratio": rr_ratio,
                "atr_sl_mult": atr_sl_mult,
                "breakout_buffer_atr": breakout_buffer,
                "body_ratio_min": body_ratio,
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
                "passes_ftmo": result.passes_ftmo_filter(),
            }
            best.append(row)

        except Exception as e:
            print(f"Error en combinación {idx}: {e}")

    if not best:
        print("No hubo resultados.")
        return

    best_sorted = sorted(
        best,
        key=lambda x: (
            x["passes_ftmo"],
            x["profit_factor"],
            x["sharpe"],
            x["total_return_pct"],
            -x["max_dd_pct"],
        ),
        reverse=True
    )

    print("\n=== TOP 20 RESULTADOS ===")
    for row in best_sorted[:20]:
        print(row)

    approved = [r for r in best_sorted if r["passes_ftmo"]]
    print(f"\nAprobadas FTMO: {len(approved)} / {len(best_sorted)}")


if __name__ == "__main__":
    main()