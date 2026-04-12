from itertools import product
from backtest.backtester_eurjpy import EURJPYBacktester


def main():
    session_windows = [(7, 13), (7, 14)]
    adx_ranges = [(18, 50), (20, 50)]
    rr_ratios = [1.3, 1.4]
    atr_sl_mults = [1.0, 1.2]
    breakout_buffers = [0.0, 0.05]
    body_ratios = [0.25, 0.35]
    trade_modes = ["BOTH", "BUY_ONLY", "SELL_ONLY"]

    combos = list(product(
        session_windows,
        adx_ranges,
        rr_ratios,
        atr_sl_mults,
        breakout_buffers,
        body_ratios,
        trade_modes,
    ))

    print(f"Lanzando grid EURJPY reducido con {len(combos)} combinaciones...\n")

    rows = []
    min_trades_required = 30

    for idx, (
        session_window,
        adx_range,
        rr_ratio,
        atr_sl_mult,
        breakout_buffer,
        body_ratio,
        trade_mode,
    ) in enumerate(combos, start=1):
        session_start, session_end = session_window
        adx_min, adx_max = adx_range

        print(
            f"[{idx:>3}/{len(combos)}] "
            f"SESSION={session_start}-{session_end} | "
            f"ADX={adx_min}-{adx_max} | "
            f"RR={rr_ratio} | "
            f"SLxATR={atr_sl_mult} | "
            f"BUFFER={breakout_buffer} | "
            f"BODY={body_ratio} | "
            f"MODE={trade_mode}"
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
                atr_min=0.08,
                range_atr_min=0.4,
                range_atr_cap=4.0,
                trade_mode=trade_mode,
                friday_cutoff_hour=12,
            )

            result = bt.run()

            passes_ftmo_strict = (
                result.passes_ftmo_filter() and
                result.total_trades >= min_trades_required
            )

            row = {
                "session": f"{session_start}-{session_end}",
                "adx": f"{adx_min}-{adx_max}",
                "rr_ratio": rr_ratio,
                "atr_sl_mult": atr_sl_mult,
                "breakout_buffer_atr": breakout_buffer,
                "body_ratio_min": body_ratio,
                "trade_mode": trade_mode,
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
                "passes_ftmo_strict": passes_ftmo_strict,
            }
            rows.append(row)

        except Exception as e:
            print(f"Error en combinación {idx}: {e}")

    if not rows:
        print("No hubo resultados.")
        return

    rows_sorted = sorted(
        rows,
        key=lambda x: (
            x["passes_ftmo_strict"],
            x["profit_factor"],
            x["sharpe"],
            x["total_return_pct"],
            -x["max_dd_pct"],
            x["trades"],
        ),
        reverse=True
    )

    print("\n=== TOP 20 RESULTADOS ===")
    for row in rows_sorted[:20]:
        print(row)

    strict_ok = [r for r in rows_sorted if r["passes_ftmo_strict"]]
    print(f"\nAprobadas FTMO strict: {len(strict_ok)} / {len(rows_sorted)}")

    enough_trades = [r for r in rows_sorted if r["trades"] >= min_trades_required]
    print(f"Con al menos {min_trades_required} trades: {len(enough_trades)} / {len(rows_sorted)}")


if __name__ == "__main__":
    main()