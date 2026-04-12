from pathlib import Path
import pandas as pd

from backtest.backtester_usdjpy import USDJPYBacktester


CANDIDATES = [
    {"name": "A", "rr_ratio": 1.40, "buffer_pips": 0.040, "min_body_ratio": 0.50, "max_bars": 42},
    {"name": "B", "rr_ratio": 1.40, "buffer_pips": 0.040, "min_body_ratio": 0.45, "max_bars": 42},
    {"name": "C", "rr_ratio": 1.35, "buffer_pips": 0.040, "min_body_ratio": 0.50, "max_bars": 42},
]

IS_START = "2024-12-01"
IS_END = "2025-09-30 23:59:59"
OOS_START = "2025-10-01"
OOS_END = "2026-04-30 23:59:59"


def run_candidate(candidate: dict, start_date: str, end_date: str, label: str):
    bt = USDJPYBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=candidate["rr_ratio"],
        symbol="USDJPY",
        start_date=start_date,
        end_date=end_date,
    )
    bt.BUFFER_PIPS = candidate["buffer_pips"]
    bt.MIN_BODY_RATIO = candidate["min_body_ratio"]
    bt.MAX_BARS_IN_TRADE = candidate["max_bars"]

    result = bt.run()
    stats = getattr(result, "extra_stats", {}) or {}

    return {
        "candidate": candidate["name"],
        "segment": label,
        "start_date": start_date,
        "end_date": end_date,
        "rr_ratio": candidate["rr_ratio"],
        "buffer_pips": candidate["buffer_pips"],
        "min_body_ratio": candidate["min_body_ratio"],
        "max_bars_in_trade": candidate["max_bars"],
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
        "tp_count": int(stats.get("tp", 0)),
        "sl_count": int(stats.get("sl", 0)),
        "breakeven_count": int(stats.get("breakeven", 0)),
        "timeout_count": int(stats.get("timeout", 0)),
        "trades_detail": pd.DataFrame(bt.last_trades_detail),
    }


def main():
    out_dir = Path("backtest/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for candidate in CANDIDATES:
        print(f"\n{'=' * 60}")
        print(f"CANDIDATO {candidate['name']} | IS")
        print(f"{'=' * 60}")
        is_row = run_candidate(candidate, IS_START, IS_END, "IS")
        rows.append({k: v for k, v in is_row.items() if k != "trades_detail"})

        print(f"\n{'=' * 60}")
        print(f"CANDIDATO {candidate['name']} | OOS")
        print(f"{'=' * 60}")
        oos_row = run_candidate(candidate, OOS_START, OOS_END, "OOS")
        rows.append({k: v for k, v in oos_row.items() if k != "trades_detail"})

        is_trades = is_row["trades_detail"].copy()
        oos_trades = oos_row["trades_detail"].copy()
        if not is_trades.empty:
            is_trades["segment"] = "IS"
            is_trades["candidate"] = candidate["name"]
        if not oos_trades.empty:
            oos_trades["segment"] = "OOS"
            oos_trades["candidate"] = candidate["name"]

        trades_all = pd.concat([is_trades, oos_trades], ignore_index=True)
        trades_file = out_dir / f"usdjpy_candidate_{candidate['name']}_oos_trades.csv"
        trades_all.to_csv(trades_file, index=False)

    df = pd.DataFrame(rows)
    summary_file = out_dir / "usdjpy_oos_validation_summary.csv"
    df.to_csv(summary_file, index=False)

    print("\n=== RESUMEN OOS ===")
    print(df.to_string(index=False))
    print(f"\nResumen guardado en: {summary_file}")


if __name__ == "__main__":
    main()