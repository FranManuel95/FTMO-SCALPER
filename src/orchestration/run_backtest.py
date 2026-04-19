"""
Script principal de backtest para una estrategia dada.

Uso:
  python -m src.orchestration.run_backtest --strategy breakout --symbol XAUUSD
  python -m src.orchestration.run_backtest --strategy breakout --symbol XAUUSD --no-htf
  python -m src.orchestration.run_backtest --strategy breakout --symbol XAUUSD --diagnostic

Fuente de datos (en orden de prioridad):
  1. CSVs locales de MetaTrader 5 (backtest/data/ o data/raw/)
  2. Yahoo Finance como fallback (solo datos recientes)
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


def get_loader(symbol: str, timeframe: str, data_dir: str | None = None):
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
    tz_offset: int = 2,
    htf_trend: bool = True,
    diagnostic: bool = False,
    research: bool = False,
    adx_min: float | None = None,
    rr_target: float | None = None,
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
        cfg = LondonBreakoutConfig(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        htf_label = f"H4 trend {'ON' if htf_trend else 'OFF'}"
        print(f"[signals] Asian: {cfg.asian_start_h:02d}:00-{cfg.asian_end_h:02d}:00 | London: {cfg.london_start_h:02d}:00-{cfg.london_end_h:02d}:00 | {htf_label}")
        result = generate_london_breakout_signals(df, cfg, return_diagnostics=diagnostic)
        if diagnostic:
            signals, diag_rows = result
        else:
            signals = result
            diag_rows = []
    elif strategy == "pullback":
        from src.signals.pullback.trend_pullback import TrendPullbackConfig, generate_pullback_signals
        pb_kwargs = dict(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        if adx_min is not None:
            pb_kwargs["adx_min"] = adx_min
        if rr_target is not None:
            pb_kwargs["rr_target"] = rr_target
        pb_cfg = TrendPullbackConfig(**pb_kwargs)
        s_start = (7 + tz_offset) % 24
        s_end = (21 + tz_offset) % 24
        session_label = f"Session {s_start:02d}:00-{s_end:02d}:00" if pb_cfg.session_filter else "24/5"
        htf_label = f"H4 trend {'ON' if htf_trend else 'OFF'}"
        print(f"[signals] {session_label} | {htf_label} | ADX>{pb_cfg.adx_min} | RR {pb_cfg.rr_target}")
        signals = generate_pullback_signals(df, pb_cfg)
        diag_rows = []
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    print(f"[signals] {len(signals)} señales generadas")

    daily_guard = DailyLossGuard(initial_balance)
    max_guard = MaxLossGuard(initial_balance)

    if research:
        print("[mode] RESEARCH — MaxLossGuard desactivado para ver performance completa")

    trades: list[Trade] = []
    trade_log: list[dict] = []

    for sig in signals:
        if not research and max_guard.is_triggered():
            print("[risk] MaxLossGuard activado — deteniendo simulación")
            break
        if not research and daily_guard.is_blocked(sig.timestamp):
            continue

        size = size_by_fixed_risk(initial_balance, risk_pct, sig.entry_price, sig.stop_loss)

        future = df[df.index > sig.timestamp]
        exit_price = None
        exit_time = None
        outcome = "open"
        bars_to_exit = 0

        for ts, bar in future.iterrows():
            bars_to_exit += 1
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
                "entry": round(sig.entry_price, 3),
                "sl": round(sig.stop_loss, 3),
                "tp": round(sig.take_profit, 3),
                "exit": round(exit_price, 3),
                "outcome": outcome,
                "pnl": round(trade.pnl, 2),
                "bars_to_exit": bars_to_exit,
            })

        trades.append(trade)

    results = {
        "symbol": symbol,
        "strategy": strategy,
        "period": f"{start} to {end}",
        "timeframe": timeframe,
        "tz_offset_hours": tz_offset,
        "htf_trend_filter": htf_trend,
        "total_signals": len(signals),
        "total_trades": len([t for t in trades if t.exit_time is not None]),
        "performance": summary(trades, initial_balance),
        "ftmo_checks": run_all_checks(trades, initial_balance),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_dir = REPORTS_DIR / "strategy_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{'htf' if htf_trend else 'nohtf'}"
    base = f"{symbol}_{strategy}_{timeframe}_{tag}"

    with open(report_dir / f"{base}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    if trade_log:
        log_path = report_dir / f"{base}_trades.csv"
        with open(log_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=trade_log[0].keys())
            writer.writeheader()
            writer.writerows(trade_log)
        print(f"[report] Trade log: {log_path}")

    if diagnostic and diag_rows:
        diag_path = report_dir / f"{base}_diagnostic.csv"
        diag_fields = ["ts", "reason", "side", "close", "entry", "sl", "tp",
                       "asian_range", "atr", "adx", "htf_trend", "rr"]
        with open(diag_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=diag_fields, extrasaction="ignore")
            writer.writeheader()
            # Normalizar filas: rellenar campos faltantes con ""
            writer.writerows({k: row.get(k, "") for k in diag_fields} for row in diag_rows)
        print(f"[report] Diagnóstico: {diag_path}")

    print(f"[report] Guardado en {report_dir / f'{base}.json'}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest — Trading Research Lab")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--strategy", default="breakout", choices=["breakout", "pullback"])
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--balance", type=float, default=10000.0)
    parser.add_argument("--risk", type=float, default=0.01)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--tz-offset", type=int, default=2)
    parser.add_argument("--no-htf", action="store_true", help="Desactivar filtro de tendencia H4")
    parser.add_argument("--diagnostic", action="store_true", help="Guardar CSV con motivo de cada señal rechazada")
    parser.add_argument("--research", action="store_true", help="Desactivar guards para ver performance completa del año")
    parser.add_argument("--adx-min", type=float, default=None, help="ADX mínimo (default: 20)")
    parser.add_argument("--rr-target", type=float, default=None, help="Ratio RR objetivo (default: 2.0)")
    args = parser.parse_args()

    results = run_backtest(
        args.symbol, args.strategy, args.start, args.end,
        args.timeframe, args.balance, args.risk, args.data_dir,
        args.tz_offset, not args.no_htf, args.diagnostic, args.research,
        args.adx_min, args.rr_target,
    )
    print(json.dumps(results, indent=2, default=str))
