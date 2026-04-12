# backtest/run_usdjpy_m5_global_grid.py

from itertools import product
from pathlib import Path
import pandas as pd

from backtest.backtester_usdjpy import USDJPYBacktester


def main():
    initial_balance = 10000
    risk_per_trade = 0.005
    symbol = "USDJPY"

    # Grid reducido pero útil: evita miles de combinaciones basura
    rr_values = [1.2, 1.4, 1.6]
    adx_min_values = [16, 18, 20]
    adx_max_values = [35, 42, 50]
    atr_sl_mult_values = [1.0, 1.25, 1.5]
    atr_min_values = [0.035, 0.045, 0.055]
    buffer_values = [0.02, 0.03, 0.05]
    body_ratio_values = [0.45, 0.55, 0.65]
    break_even_values = [0.7, 0.9, 1.1]
    max_bars_values = [18, 24, 30]

    combos = list(product(
        rr_values,
        adx_min_values,
        adx_max_values,
        atr_sl_mult_values,
        atr_min_values,
        buffer_values,
        body_ratio_values,
        break_even_values,
        max_bars_values
    ))

    print(f"Lanzando grid global USDJPY M5 con {len(combos)} combinaciones...")

    rows = []

    for idx, (
        rr,
        adx_min,
        adx_max,
        atr_sl_mult,
        atr_min,
        buffer_pips,
        min_body_ratio,
        break_even_r,
        max_bars
    ) in enumerate(combos, start=1):

        if adx_min >= adx_max:
            continue

        print(
            f"[{idx:>4}/{len(combos)}] "
            f"RR={rr} | ADX={adx_min}-{adx_max} | ATR_SL={atr_sl_mult} | "
            f"ATR_MIN={atr_min} | BUFFER={buffer_pips} | BODY={min_body_ratio} | "
            f"BE={break_even_r} | HOLD={max_bars}"
        )

        try:
            bt = USDJPYBacktester(
                initial_balance=initial_balance,
                risk_per_trade=risk_per_trade,
                rr_ratio=rr,
                symbol=symbol
            )

            # Override dinámico de parámetros
            bt.ADX_MIN = adx_min
            bt.ADX_MAX = adx_max
            bt.ATR_SL_MULT = atr_sl_mult
            bt.ATR_MIN = atr_min
            bt.BUFFER_PIPS = buffer_pips
            bt.MIN_BODY_RATIO = min_body_ratio
            bt.BREAK_EVEN_R = break_even_r
            bt.MAX_BARS_IN_TRADE = max_bars

            result = bt.run()

            rows.append({
                "rr_ratio": rr,
                "adx_min": adx_min,
                "adx_max": adx_max,
                "atr_sl_mult": atr_sl_mult,
                "atr_min": atr_min,
                "buffer_pips": buffer_pips,
                "min_body_ratio": min_body_ratio,
                "break_even_r": break_even_r,
                "max_bars_in_trade": max_bars,
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "max_drawdown": result.max_drawdown,
                "total_return": result.total_return,
                "avg_win": result.avg_win,
                "avg_loss": result.avg_loss,
                "expectancy": result.expectancy,
            })

        except Exception as e:
            print(f"   -> Error en combinación: {e}")

    if not rows:
        raise ValueError("No hubo resultados válidos.")

    df = pd.DataFrame(rows)

    # Score orientado a FTMO: prioriza retorno con DD bajo y PF decente
    df["score_ftmo"] = (
        (df["total_return"] * 100)
        + (df["profit_factor"] * 8)
        + (df["sharpe_ratio"] * 3)
        + (df["sortino_ratio"] * 2)
        + (df["win_rate"] * 10)
        - (df["max_drawdown"] * 100 * 2.2)
    )

    # Penalizaciones por pocos trades o resultados poco robustos
    df.loc[df["total_trades"] < 25, "score_ftmo"] -= 12
    df.loc[df["profit_factor"] < 1.15, "score_ftmo"] -= 10
    df.loc[df["max_drawdown"] > 0.08, "score_ftmo"] -= 15

    df = df.sort_values(
        by=["score_ftmo", "profit_factor", "total_return"],
        ascending=False
    ).reset_index(drop=True)

    out_dir = Path("backtest/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / "usdjpy_m5_global_grid_results.csv"
    df.to_csv(out_file, index=False)

    print("\nTop 20 combinaciones:")
    print(df.head(20).to_string(index=False))
    print(f"\nResultados guardados en: {out_file}")


if __name__ == "__main__":
    main()