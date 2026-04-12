from itertools import product
from pathlib import Path
import pandas as pd

from backtest.backtester_usdjpy import USDJPYBacktester


def main():
    initial_balance = 10000
    risk_per_trade = 0.005
    symbol = "USDJPY"

    # Fine grid alrededor de la mejor zona encontrada
    rr_values = [1.35, 1.40, 1.45, 1.50]
    buffer_values = [0.035, 0.040, 0.045, 0.050]
    body_ratio_values = [0.45, 0.50, 0.55]
    max_bars_values = [36, 42, 48]

    combos = list(product(
        rr_values,
        buffer_values,
        body_ratio_values,
        max_bars_values,
    ))

    print(f"Lanzando fine-grid USDJPY M5 con {len(combos)} combinaciones...")

    rows = []

    for idx, (
        rr,
        buffer_pips,
        min_body_ratio,
        max_bars
    ) in enumerate(combos, start=1):

        print(
            f"[{idx:>3}/{len(combos)}] "
            f"RR={rr} | BUFFER={buffer_pips} | BODY={min_body_ratio} | HOLD={max_bars}"
        )

        try:
            bt = USDJPYBacktester(
                initial_balance=initial_balance,
                risk_per_trade=risk_per_trade,
                rr_ratio=rr,
                symbol=symbol
            )

            bt.BUFFER_PIPS = buffer_pips
            bt.MIN_BODY_RATIO = min_body_ratio
            bt.MAX_BARS_IN_TRADE = max_bars

            result = bt.run()
            stats = getattr(result, "extra_stats", {}) or {}

            tp_count = int(stats.get("tp", 0))
            sl_count = int(stats.get("sl", 0))
            be_count = int(stats.get("breakeven", 0))
            timeout_count = int(stats.get("timeout", 0))

            rows.append({
                "rr_ratio": rr,
                "buffer_pips": buffer_pips,
                "min_body_ratio": min_body_ratio,
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

                "tp_count": tp_count,
                "sl_count": sl_count,
                "breakeven_count": be_count,
                "timeout_count": timeout_count,
            })

        except Exception as e:
            print(f"   -> Error en combinación: {e}")

    if not rows:
        raise ValueError("No hubo resultados válidos en el fine-grid.")

    df = pd.DataFrame(rows)

    # Score orientado a FTMO
    df["score_ftmo"] = (
        (df["profit_factor"] * 14)
        + (df["total_return"] * 100)
        + (df["expectancy"] / 2)
        + (df["win_rate"] * 10)
        - (df["max_drawdown"] * 100 * 2.75)
    )

    # Penalizaciones por muestra muy corta o setup poco fiable
    df.loc[df["total_trades"] < 12, "score_ftmo"] -= 8
    df.loc[df["total_trades"] < 10, "score_ftmo"] -= 12
    df.loc[df["profit_factor"] < 1.0, "score_ftmo"] -= 12
    df.loc[df["max_drawdown"] > 0.05, "score_ftmo"] -= 10

    # Métrica auxiliar por si luego quieres filtrar setups "limpios"
    df["timeout_ratio"] = df["timeout_count"] / df["total_trades"].replace(0, 1)
    df["sl_ratio"] = df["sl_count"] / df["total_trades"].replace(0, 1)
    df["tp_ratio"] = df["tp_count"] / df["total_trades"].replace(0, 1)

    df = df.sort_values(
        by=["score_ftmo", "profit_factor", "total_return", "expectancy"],
        ascending=False
    ).reset_index(drop=True)

    out_dir = Path("backtest/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / "usdjpy_m5_fine_grid_results.csv"
    df.to_csv(out_file, index=False)

    print("\n=== TOP 25 FINE-GRID USDJPY ===")
    print(df.head(25).to_string(index=False))
    print(f"\nResultados guardados en: {out_file}")


if __name__ == "__main__":
    main()
    