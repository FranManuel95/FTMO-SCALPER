"""
Combined backtest: London Breakout (15m) + Trend Pullback (1h) en XAUUSD.

Las señales de ambas estrategias comparten un único DailyLossGuard + MaxLossGuard.
Los exits se simulan con datos 15m (mayor resolución) para ambos tipos de señal.

Uso:
  python -m src.orchestration.run_combined --start 2023-01-01 --end 2025-01-01

Para walk-forward:
  python -m src.orchestration.run_validation --symbol XAUUSD --strategy combined \\
    --start 2022-01-01 --end 2025-01-01 --risk 0.005 --adx-min 25 --rr-target 2.5
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.logging import setup_logging
from src.core.paths import REPORTS_DIR
from src.core.types import Side, Trade
from src.data.loaders.mt5_csv import MT5CsvLoader, find_csv
from src.data.loaders.yahoo import YahooLoader
from src.metrics.ftmo_checks import run_all_checks
from src.metrics.performance import summary
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.max_loss_guard import MaxLossGuard
from src.risk.position_sizing import size_by_fixed_risk
from src.signals.breakout.london_breakout import LondonBreakoutConfig, generate_london_breakout_signals
from src.signals.pullback.trend_pullback import TrendPullbackConfig, generate_pullback_signals


def _get_loader(symbol: str, timeframe: str, data_dir: str | None = None):
    if find_csv(symbol, timeframe) is not None:
        return MT5CsvLoader(data_dir)
    return YahooLoader()


def run_combined_backtest(
    symbol: str,
    start: str,
    end: str,
    initial_balance: float = 10000.0,
    risk_pct: float = 0.005,
    adx_min: float = 25.0,
    rr_target: float = 2.5,
    tz_offset: int = 2,
    research: bool = False,
    data_dir: str | None = None,
    daily_trend: bool = True,
) -> dict:
    setup_logging()

    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)

    loader_15m = _get_loader(symbol, "15m", data_dir)
    loader_1h = _get_loader(symbol, "1h", data_dir)

    df_15m = loader_15m.load(symbol, start=start_dt, end=end_dt, timeframe="15m")
    df_1h = loader_1h.load(symbol, start=start_dt, end=end_dt, timeframe="1h")
    df_15m.attrs["symbol"] = symbol
    df_1h.attrs["symbol"] = symbol

    print(f"[data] 15m: {len(df_15m)} velas | 1h: {len(df_1h)} velas")

    bo_cfg = LondonBreakoutConfig(
        tz_offset_hours=tz_offset,
        rr_target=rr_target,
        htf_trend_enabled=True,
        daily_trend_enabled=daily_trend,
    )
    pb_cfg = TrendPullbackConfig(
        tz_offset_hours=tz_offset,
        adx_min=adx_min,
        rr_target=rr_target,
        htf_trend_enabled=True,
        daily_trend_enabled=daily_trend,
    )
    dt_label = "DailyEMA ON" if daily_trend else "DailyEMA OFF"
    print(f"[config] ADX>{adx_min} | RR {rr_target} | {dt_label}")

    bo_signals = generate_london_breakout_signals(df_15m, bo_cfg)
    pb_signals = generate_pullback_signals(df_1h, pb_cfg)
    all_signals = sorted(bo_signals + pb_signals, key=lambda s: s.timestamp)

    print(f"[signals] Breakout: {len(bo_signals)} | Pullback: {len(pb_signals)} | Total: {len(all_signals)}")
    if research:
        print("[mode] RESEARCH — MaxLossGuard desactivado")

    daily_guard = DailyLossGuard(initial_balance)
    max_guard = MaxLossGuard(initial_balance)

    trades: list[Trade] = []
    trade_log: list[dict] = []

    for sig in all_signals:
        if not research and max_guard.is_triggered():
            print("[risk] MaxLossGuard activado — deteniendo")
            break
        if not research and daily_guard.is_blocked(sig.timestamp):
            continue

        size = size_by_fixed_risk(initial_balance, risk_pct, sig.entry_price, sig.stop_loss)
        future = df_15m[df_15m.index > sig.timestamp]

        exit_price = exit_time = None
        outcome = "open"
        bars = 0

        for ts, bar in future.iterrows():
            bars += 1
            if sig.side == Side.LONG:
                if bar["low"] <= sig.stop_loss:
                    exit_price, exit_time, outcome = sig.stop_loss, ts, "SL"
                    break
                if bar["high"] >= sig.take_profit:
                    exit_price, exit_time, outcome = sig.take_profit, ts, "TP"
                    break
            else:
                if bar["high"] >= sig.stop_loss:
                    exit_price, exit_time, outcome = sig.stop_loss, ts, "SL"
                    break
                if bar["low"] <= sig.take_profit:
                    exit_price, exit_time, outcome = sig.take_profit, ts, "TP"
                    break

        trade = Trade(
            symbol=symbol,
            side=sig.side,
            entry_time=sig.timestamp,
            entry_price=sig.entry_price,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            size=size,
        )

        if exit_price and exit_time:
            trade.close(exit_time, exit_price)
            daily_guard.record_pnl(trade.pnl, exit_time)
            max_guard.update(trade.pnl)
            trade_log.append({
                "entry_time": str(sig.timestamp),
                "exit_time": str(exit_time),
                "side": sig.side.value,
                "strategy": sig.signal_type.value,
                "entry": round(sig.entry_price, 3),
                "sl": round(sig.stop_loss, 3),
                "tp": round(sig.take_profit, 3),
                "exit": round(exit_price, 3),
                "outcome": outcome,
                "pnl": round(trade.pnl, 2),
                "bars_to_exit": bars,
            })

        trades.append(trade)

    results = {
        "symbol": symbol,
        "strategy": "combined",
        "period": f"{start} to {end}",
        "timeframe": "15m+1h",
        "bo_signals": len(bo_signals),
        "pb_signals": len(pb_signals),
        "total_signals": len(all_signals),
        "total_trades": len([t for t in trades if t.exit_time is not None]),
        "performance": summary(trades, initial_balance),
        "ftmo_checks": run_all_checks(trades, initial_balance),
        "trade_pnls": [round(t["pnl"], 4) for t in trade_log],
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_dir = REPORTS_DIR / "strategy_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    base = f"{symbol}_combined"

    with open(report_dir / f"{base}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    if trade_log:
        log_path = report_dir / f"{base}_trades.csv"
        with open(log_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=trade_log[0].keys())
            writer.writeheader()
            writer.writerows(trade_log)
        print(f"[report] Trade log: {log_path}")

    print(f"[report] Guardado en {report_dir / f'{base}.json'}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combined Backtest — Breakout 15m + Pullback 1h")
    parser.add_argument("--symbol",     default="XAUUSD")
    parser.add_argument("--start",      default="2023-01-01")
    parser.add_argument("--end",        default="2025-01-01")
    parser.add_argument("--balance",    type=float, default=10000.0)
    parser.add_argument("--risk",       type=float, default=0.005)
    parser.add_argument("--adx-min",    type=float, default=25.0)
    parser.add_argument("--rr-target",  type=float, default=2.5)
    parser.add_argument("--tz-offset",  type=int,   default=2)
    parser.add_argument("--research",   action="store_true")
    args = parser.parse_args()

    res = run_combined_backtest(
        symbol=args.symbol, start=args.start, end=args.end,
        initial_balance=args.balance, risk_pct=args.risk,
        adx_min=args.adx_min, rr_target=args.rr_target,
        tz_offset=args.tz_offset, research=args.research,
    )
    print(json.dumps(res, indent=2, default=str))
