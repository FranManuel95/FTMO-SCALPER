"""
Script principal de backtest para una estrategia dada.
Uso: python -m src.orchestration.run_backtest --strategy breakout --symbol XAUUSD
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.core.logging import setup_logging
from src.core.paths import PROCESSED_DIR, REPORTS_DIR
from src.core.types import Side, Trade, TradeStatus
from src.data.loaders.yahoo import YahooLoader
from src.metrics.ftmo_checks import run_all_checks
from src.metrics.performance import summary
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.max_loss_guard import MaxLossGuard
from src.risk.position_sizing import size_by_fixed_risk


def run_backtest(
    symbol: str,
    strategy: str,
    start: str,
    end: str,
    timeframe: str = "15m",
    initial_balance: float = 10000.0,
    risk_pct: float = 0.01,
) -> dict:
    setup_logging()

    loader = YahooLoader()
    df = loader.load(
        symbol,
        start=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        end=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        timeframe=timeframe,
    )
    df.attrs["symbol"] = symbol

    if strategy == "breakout":
        from src.signals.breakout.london_breakout import generate_london_breakout_signals
        signals = generate_london_breakout_signals(df)
    elif strategy == "pullback":
        from src.signals.pullback.trend_pullback import generate_pullback_signals
        signals = generate_pullback_signals(df)
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    daily_guard = DailyLossGuard(initial_balance)
    max_guard = MaxLossGuard(initial_balance)

    trades: list[Trade] = []
    for sig in signals:
        if max_guard.is_triggered():
            break
        if daily_guard.is_blocked(sig.timestamp):
            continue

        size = size_by_fixed_risk(initial_balance, risk_pct, sig.entry_price, sig.stop_loss)

        future = df[df.index > sig.timestamp]
        exit_price = None
        exit_time = None

        for ts, bar in future.iterrows():
            if sig.side == Side.LONG:
                if bar["low"] <= sig.stop_loss:
                    exit_price, exit_time = sig.stop_loss, ts
                    break
                if bar["high"] >= sig.take_profit:
                    exit_price, exit_time = sig.take_profit, ts
                    break
            else:
                if bar["high"] >= sig.stop_loss:
                    exit_price, exit_time = sig.stop_loss, ts
                    break
                if bar["low"] <= sig.take_profit:
                    exit_price, exit_time = sig.take_profit, ts
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

        trades.append(trade)

    results = {
        "symbol": symbol,
        "strategy": strategy,
        "period": f"{start} to {end}",
        "timeframe": timeframe,
        "total_signals": len(signals),
        "performance": summary(trades, initial_balance),
        "ftmo_checks": run_all_checks(trades, initial_balance),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "strategy_reports" / f"{symbol}_{strategy}_{timeframe}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--strategy", default="breakout")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--risk", type=float, default=0.01)
    args = parser.parse_args()

    results = run_backtest(args.symbol, args.strategy, args.start, args.end, args.timeframe, args.balance, args.risk)
    print(json.dumps(results, indent=2, default=str))
