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
    daily_adx_min: float | None = None,
    weekly_regime: bool = False,
    rsi_oversold: float | None = None,
    rsi_overbought: float | None = None,
    bb_std: float | None = None,
    exit_mode: str = "fixed",        # "fixed" | "partial" | "trail"
    partial_tp_r: float = 1.5,       # first TP level (in R multiples) for "partial"
    trail_atr_mult: float = 1.0,     # ATR multiplier for trailing stop
    long_only: bool = False,         # only generate LONG signals (pullback strategy)
    commission_per_lot: float = 0.0, # round-trip transaction cost in USD per standard lot
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
    from src.features.technical.indicators import add_atr as _add_atr
    df = _add_atr(df, 14)   # needed for trailing stop exit mode
    print(f"[data] Cargadas {len(df)} velas de {symbol} {timeframe} ({df.index[0]} → {df.index[-1]})")

    if strategy == "breakout":
        from src.signals.breakout.london_breakout import LondonBreakoutConfig, generate_london_breakout_signals
        cfg = LondonBreakoutConfig(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend,
                                   weekly_regime_enabled=weekly_regime)
        htf_label = f"H4 trend {'ON' if htf_trend else 'OFF'}"
        weekly_label = "WeeklyEMA ON" if weekly_regime else "WeeklyEMA OFF"
        print(f"[signals] Asian: {cfg.asian_start_h:02d}:00-{cfg.asian_end_h:02d}:00 | London: {cfg.london_start_h:02d}:00-{cfg.london_end_h:02d}:00 | {htf_label} | {weekly_label}")
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
        if daily_adx_min is not None:
            pb_kwargs["daily_adx_min"] = daily_adx_min
        if weekly_regime:
            pb_kwargs["weekly_regime_enabled"] = True
        if long_only:
            pb_kwargs["long_only"] = True
        pb_cfg = TrendPullbackConfig(**pb_kwargs)
        s_start = (7 + tz_offset) % 24
        s_end = (21 + tz_offset) % 24
        session_label = f"Session {s_start:02d}:00-{s_end:02d}:00" if pb_cfg.session_filter else "24/5"
        htf_label = f"H4 trend {'ON' if htf_trend else 'OFF'}"
        daily_label = f"DailyADX>{pb_cfg.daily_adx_min}" if pb_cfg.daily_adx_min > 0 else "DailyADX OFF"
        weekly_label = "WeeklyEMA ON" if weekly_regime else "WeeklyEMA OFF"
        print(f"[signals] {session_label} | {htf_label} | {daily_label} | {weekly_label} | ADX>{pb_cfg.adx_min} | RR {pb_cfg.rr_target}")
        signals = generate_pullback_signals(df, pb_cfg)
        diag_rows = []
    elif strategy == "mean_reversion":
        from src.signals.mean_reversion.bb_reversion import BBReversionConfig, generate_bb_reversion_signals
        mr_kwargs: dict = dict(tz_offset_hours=tz_offset)
        if adx_min is not None:
            mr_kwargs["adx_max"] = adx_min   # adx_min re-usado como adx_max para mean reversion
        if rr_target is not None:
            mr_kwargs["rr_target"] = rr_target
        if rsi_oversold is not None:
            mr_kwargs["rsi_oversold"] = rsi_oversold
        if rsi_overbought is not None:
            mr_kwargs["rsi_overbought"] = rsi_overbought
        if bb_std is not None:
            mr_kwargs["bb_std"] = bb_std
        mr_cfg = BBReversionConfig(**mr_kwargs)
        print(f"[signals] MeanReversion BB({mr_cfg.bb_period},{mr_cfg.bb_std}) | RSI oversold<{mr_cfg.rsi_oversold} overbought>{mr_cfg.rsi_overbought} | ADX<{mr_cfg.adx_max} | RR {mr_cfg.rr_target}")
        signals = generate_bb_reversion_signals(df, mr_cfg)
        diag_rows = []
    elif strategy == "fvg":
        from src.signals.fvg.fair_value_gap import FVGConfig, generate_fvg_signals
        fvg_kwargs: dict = dict(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        if adx_min is not None:
            fvg_kwargs["adx_min"] = adx_min
        if rr_target is not None:
            fvg_kwargs["rr_target"] = rr_target
        fvg_cfg = FVGConfig(**fvg_kwargs)
        print(f"[signals] FVG | ADX>{fvg_cfg.adx_min} | H4 trend {'ON' if htf_trend else 'OFF'} | RR {fvg_cfg.rr_target} | maxBars {fvg_cfg.max_bars_to_fill}")
        signals = generate_fvg_signals(df, fvg_cfg)
        diag_rows = []
    elif strategy == "london_open":
        from src.signals.breakout.london_open_breakout import LondonOpenBreakoutConfig, generate_london_open_breakout_signals
        lo_kwargs: dict = dict(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        if adx_min is not None:
            lo_kwargs["adx_min"] = adx_min
        if rr_target is not None:
            lo_kwargs["rr_target"] = rr_target
        lo_cfg = LondonOpenBreakoutConfig(**lo_kwargs)
        print(f"[signals] London ORB | Range {lo_cfg.range_start_utc:02d}:00-{lo_cfg.range_end_utc:02d}:00 UTC | ADX>{lo_cfg.adx_min} | H4 trend {'ON' if htf_trend else 'OFF'} | RR {lo_cfg.rr_target}")
        signals = generate_london_open_breakout_signals(df, lo_cfg)
        diag_rows = []
    elif strategy == "ny_breakout":
        from src.signals.breakout.ny_open_breakout import NYOpenBreakoutConfig, generate_ny_open_breakout_signals
        ny_kwargs: dict = dict(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        if adx_min is not None:
            ny_kwargs["adx_min"] = adx_min
        if rr_target is not None:
            ny_kwargs["rr_target"] = rr_target
        ny_cfg = NYOpenBreakoutConfig(**ny_kwargs)
        rng_s = f"{ny_cfg.range_start_utc:02d}:{ny_cfg.range_start_min:02d}"
        rng_e = f"{ny_cfg.range_end_utc:02d}:{ny_cfg.range_end_min:02d}"
        print(f"[signals] NY ORB | Range {rng_s}-{rng_e} UTC | ADX>{ny_cfg.adx_min} | H4 trend {'ON' if htf_trend else 'OFF'} | RR {ny_cfg.rr_target}")
        signals = generate_ny_open_breakout_signals(df, ny_cfg)
        diag_rows = []
    elif strategy == "asian_orb":
        from src.signals.breakout.asian_session_orb import AsianSessionORBConfig, generate_asian_session_orb_signals
        as_kwargs: dict = dict(tz_offset_hours=tz_offset, htf_trend_enabled=htf_trend)
        if adx_min is not None:
            as_kwargs["adx_min"] = adx_min
        if rr_target is not None:
            as_kwargs["rr_target"] = rr_target
        as_cfg = AsianSessionORBConfig(**as_kwargs)
        print(f"[signals] Asian ORB | Range 23:00-{as_cfg.asian_end_hour_utc:02d}:00 UTC | Entry {as_cfg.entry_start_utc:02d}:00-{as_cfg.entry_end_utc:02d}:00 UTC | ADX>{as_cfg.adx_min} | H4 trend {'ON' if htf_trend else 'OFF'} | RR {as_cfg.rr_target}")
        signals = generate_asian_session_orb_signals(df, as_cfg)
        diag_rows = []
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")

    print(f"[signals] {len(signals)} señales generadas")

    # Lot size: metals 100 oz/lot, everything else 100,000 units/lot
    _lot_size = 100.0 if symbol.upper().startswith("XAU") else 100_000.0

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

        risk_dist = abs(sig.entry_price - sig.stop_loss)
        sl = sig.stop_loss           # mutable SL for trailing / breakeven logic
        partial_locked = False       # partial TP already hit
        partial_pnl_r = 0.0          # R captured in partial exit

        # Precompute ATR for trail mode (use last ATR value from pre-signal data)
        trail_atr = 0.0
        if exit_mode == "trail" and "atr_14" in df.columns:
            pre = df[df.index <= sig.timestamp]["atr_14"].dropna()
            trail_atr = float(pre.iloc[-1]) if len(pre) > 0 else risk_dist * 0.5

        for ts, bar in future.iterrows():
            bars_to_exit += 1
            if sig.side == Side.LONG:
                # ── check SL first ──
                if bar["low"] <= sl:
                    if partial_locked:
                        # 50% locked at partial_tp_r, rest exits at breakeven SL
                        combined_r = 0.5 * partial_pnl_r + 0.5 * ((sl - sig.entry_price) / risk_dist)
                        exit_price = sig.entry_price + combined_r * risk_dist
                        outcome = "SL_PARTIAL"
                    else:
                        exit_price = sl
                        outcome = "SL"
                    exit_time = ts
                    break
                # ── partial TP (first target) ──
                if exit_mode == "partial" and not partial_locked:
                    p_tp = sig.entry_price + partial_tp_r * risk_dist
                    if bar["high"] >= p_tp:
                        partial_locked = True
                        partial_pnl_r = partial_tp_r
                        sl = sig.entry_price      # move SL to breakeven
                        continue                  # keep running for full TP
                # ── trail: ratchet SL up ──
                if exit_mode == "trail" and trail_atr > 0:
                    trail_sl = bar["high"] - trail_atr * trail_atr_mult
                    if trail_sl > sl:
                        sl = trail_sl
                # ── full TP ──
                if bar["high"] >= sig.take_profit:
                    if partial_locked:
                        combined_r = 0.5 * partial_pnl_r + 0.5 * sig.risk_reward
                        exit_price = sig.entry_price + combined_r * risk_dist
                        outcome = "TP_PARTIAL"
                    else:
                        exit_price = sig.take_profit
                        outcome = "TP"
                    exit_time = ts
                    break
            else:  # SHORT
                if bar["high"] >= sl:
                    if partial_locked:
                        combined_r = 0.5 * partial_pnl_r + 0.5 * ((sig.entry_price - sl) / risk_dist)
                        exit_price = sig.entry_price - combined_r * risk_dist
                        outcome = "SL_PARTIAL"
                    else:
                        exit_price = sl
                        outcome = "SL"
                    exit_time = ts
                    break
                if exit_mode == "partial" and not partial_locked:
                    p_tp = sig.entry_price - partial_tp_r * risk_dist
                    if bar["low"] <= p_tp:
                        partial_locked = True
                        partial_pnl_r = partial_tp_r
                        sl = sig.entry_price
                        continue
                if exit_mode == "trail" and trail_atr > 0:
                    trail_sl = bar["low"] + trail_atr * trail_atr_mult
                    if trail_sl < sl:
                        sl = trail_sl
                if bar["low"] <= sig.take_profit:
                    if partial_locked:
                        combined_r = 0.5 * partial_pnl_r + 0.5 * sig.risk_reward
                        exit_price = sig.entry_price - combined_r * risk_dist
                        outcome = "TP_PARTIAL"
                    else:
                        exit_price = sig.take_profit
                        outcome = "TP"
                    exit_time = ts
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
            if commission_per_lot > 0:
                trade.pnl -= commission_per_lot * (trade.size / _lot_size)
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
        "commission_per_lot": commission_per_lot,
        "total_signals": len(signals),
        "total_trades": len([t for t in trades if t.exit_time is not None]),
        "performance": summary(trades, initial_balance),
        "ftmo_checks": run_all_checks(trades, initial_balance),
        "trade_pnls": [round(t["pnl"], 4) for t in trade_log],
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
    parser.add_argument("--strategy", default="breakout", choices=["breakout", "pullback", "mean_reversion", "fvg", "london_open", "ny_breakout", "asian_orb"])
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
    parser.add_argument("--adx-min", type=float, default=None, help="ADX mínimo en H1 (default: 20)")
    parser.add_argument("--rr-target", type=float, default=None, help="Ratio RR objetivo (default: 2.0)")
    parser.add_argument("--daily-adx-min", type=float, default=None, help="ADX mínimo en Daily para filtro de régimen (default: OFF)")
    parser.add_argument("--weekly-regime", action="store_true", help="Activar filtro EMA50 semanal como régimen macro")
    parser.add_argument("--exit-mode", default="fixed", choices=["fixed", "partial", "trail"], help="Modo de salida: fixed | partial | trail")
    parser.add_argument("--partial-tp-r", type=float, default=1.5, help="R para el primer TP parcial (default: 1.5)")
    parser.add_argument("--trail-atr-mult", type=float, default=1.0, help="Multiplicador ATR para trailing stop (default: 1.0)")
    parser.add_argument("--long-only", action="store_true", help="Solo señales LONG (pullback strategy)")
    parser.add_argument("--commission", type=float, default=0.0, help="Coste round-trip en USD/lot (ej: 7.0 para forex, 35.0 para XAUUSD)")
    args = parser.parse_args()

    results = run_backtest(
        args.symbol, args.strategy, args.start, args.end,
        args.timeframe, args.balance, args.risk, args.data_dir,
        args.tz_offset, not args.no_htf, args.diagnostic, args.research,
        args.adx_min, args.rr_target, args.daily_adx_min, args.weekly_regime,
        exit_mode=args.exit_mode, partial_tp_r=args.partial_tp_r, trail_atr_mult=args.trail_atr_mult,
        long_only=args.long_only, commission_per_lot=args.commission,
    )
    print(json.dumps(results, indent=2, default=str))
