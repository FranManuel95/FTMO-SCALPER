"""
Script principal de backtest para una estrategia dada.

Uso:
  python -m src.orchestration.run_backtest --strategy breakout --symbol XAUUSD
  python -m src.orchestration.run_backtest --strategy pullback --symbol EURUSD --timeframe 1h

Fuente de datos (en orden de prioridad):
  1. CSVs locales de MetaTrader 5 (backtest/data/ o data/raw/)
  2. Yahoo Finance como fallback (solo datos recientes < 60 días para intraday)
"""
import argparse
import json
from datetime import datetime, timezone

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


def get_loader(symbol: str, timeframe: str, data_dir: str | None = None):
    """Retorna el loader más apropiado: MT5 CSV si existe, Yahoo si no."""
    csv_path = find_csv(symbol, timeframe)
    if csv_path is not None:
        print(f"[data] Usando CSV local: {csv_path}")
        return MT5CsvLoader(data_dir)
    print(f"[data] No se encontró CSV local para {symbol} {timeframe}, usando Yahoo Finance")
    return YahooLoader()


def run_backtest(
    symbol: str,
    strategy: str,
    start: str,
    end: str,
    timeframe: str = "15m",
    initial_balance: float = 10000.0,
    risk_pct: float = 0.01,
    data_dir: str | None = None,
    tz_offset: int = 0,
) -> dict:
    setup_logging()

    loader = get_loader(symbol, timeframe, data_dir)
    df = loader.load(
        symbol,
        start=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        end=datetime.fromisoformat(end).replace(tzinfo=timezone.utc),
        timeframe=timeframe,
    )
    df.attrs["symbol"] = symbol
    print(f"[data] Cargadas {len(df)} velas de {symbol} {timeframe} ({df.index[0]} → {df.index[-1]})")

    if strategy == "breakout":
        from src.signals.breakout.london_breakout import LondonBreakoutConfig, generate_london_breakout_signals
        cfg = LondonBreakoutConfig(tz_offset_hours=tz_offset)
        print(f"[signals] Asian range: {cfg.asian_start_h:02d}:00-{cfg.asian_end_h:02d}:00 | London: {cfg.london_start_h:02d}:00-{cfg.london_end_h:02d}:00 (broker time)")
        signals = generate_london_breakout_signals(df, cfg)
    elif strategy == "pullback":
        from src.signals.pullback.trend_pullback import generate_pullback_signals
        signals = generate_pullback_signals(df)
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    print(f"[signals] {len(signals)} señales generadas")

    daily_guard = DailyLossGuard(initial_balance)
    max_guard = MaxLossGuard(initial_balance)

    trades: list[Trade] = []
    for sig in signals:
        if max_guard.is_triggered():
            print("[risk] MaxLossGuard activado — deteniendo simulación")
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
        "tz_offset_hours": tz_offset,
        "total_signals": len(signals),
        "total_trades": len([t for t in trades if t.exit_time is not None]),
        "performance": summary(trades, initial_balance),
        "ftmo_checks": run_all_checks(trades, initial_balance),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "strategy_reports" / f"{symbol}_{strategy}_{timeframe}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"[report] Guardado en {report_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest de estrategias Trading Research Lab")
    parser.add_argument("--symbol", default="XAUUSD", help="Símbolo (XAUUSD, EURUSD, ...)")
    parser.add_argument("--strategy", default="breakout", choices=["breakout", "pullback"])
    parser.add_argument("--start", default="2023-01-01", help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--end", default="2024-01-01", help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--timeframe", default="15m", help="Timeframe: 1m 5m 15m 30m 1h 4h 1d")
    parser.add_argument("--balance", type=float, default=10000.0, help="Capital inicial")
    parser.add_argument("--risk", type=float, default=0.01, help="Riesgo por trade (0.01 = 1%%)")
    parser.add_argument("--data-dir", default=None, help="Ruta a carpeta con CSVs de MT5")
    parser.add_argument("--tz-offset", type=int, default=2, help="Offset UTC del broker (2=UTC+2, 3=UTC+3)")
    args = parser.parse_args()

    results = run_backtest(
        args.symbol, args.strategy, args.start, args.end,
        args.timeframe, args.balance, args.risk, args.data_dir, args.tz_offset,
    )
    print(json.dumps(results, indent=2, default=str))
