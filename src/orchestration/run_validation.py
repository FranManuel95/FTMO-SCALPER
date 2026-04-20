"""
Walk-forward + Monte Carlo validation para la mejor estrategia encontrada.

Uso:
  python -m src.orchestration.run_validation --symbol XAUUSD --strategy pullback \
    --timeframe 1h --start 2022-01-01 --end 2025-01-01 \
    --risk 0.004 --adx-min 25 --rr-target 2.5

El script:
  1. Divide el periodo en ventanas IS/OOS (walk-forward anchored)
  2. Calcula WFE (Walk-Forward Efficiency) por ventana
  3. Corre Monte Carlo sobre los trades OOS combinados
  4. Imprime un resumen de viabilidad
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.logging import setup_logging
from src.orchestration.run_backtest import run_backtest
from src.validation.walk_forward import walk_forward_efficiency

_COMBINED_STRATEGY = "combined"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _months_between(a: str, b: str) -> int:
    da, db = datetime.fromisoformat(a), datetime.fromisoformat(b)
    return (db.year - da.year) * 12 + db.month - da.month


def _add_months(date_str: str, months: int) -> str:
    dt = datetime.fromisoformat(date_str)
    m = dt.month - 1 + months
    year = dt.year + m // 12
    month = m % 12 + 1
    return f"{year:04d}-{month:02d}-{dt.day:02d}"


def _build_windows(start: str, end: str, is_months: int, oos_months: int, step: int) -> list[dict]:
    windows = []
    cursor = start
    while True:
        is_end = _add_months(cursor, is_months)
        oos_end = _add_months(is_end, oos_months)
        if oos_end > end:
            break
        windows.append({"is_start": cursor, "is_end": is_end,
                        "oos_start": is_end, "oos_end": oos_end})
        cursor = _add_months(cursor, step)
    return windows


def _pf(result: dict) -> float:
    return result["performance"]["profit_factor"]


def _trades(result: dict) -> int:
    return result["performance"]["total_trades"]


def _net(result: dict) -> float:
    return result["performance"]["net_pnl"]


def _dd(result: dict) -> float:
    return result["ftmo_checks"]["max_loss_check"]["max_drawdown_pct"]


def _wr(result: dict) -> float:
    return result["performance"]["win_rate"]


# ── Monte Carlo sobre lista de PnL por trade ─────────────────────────────────

def monte_carlo_pnl(
    trade_pnls: list[float],
    initial_balance: float = 10000.0,
    n_sims: int = 5000,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    pnls = np.array(trade_pnls)
    n = len(pnls)

    sim_pnls = rng.choice(pnls, size=(n_sims, n), replace=True)
    cum = np.cumsum(sim_pnls, axis=1)
    equity = initial_balance + cum

    # Max drawdown por simulación (absoluto, positivo = peor)
    peak = np.maximum.accumulate(equity, axis=1)
    dd_pct = (equity - peak) / initial_balance
    max_dd_abs = np.abs(dd_pct.min(axis=1))

    final = cum[:, -1]

    gross_win = np.where(sim_pnls > 0, sim_pnls, 0).sum(axis=1)
    gross_loss = np.abs(np.where(sim_pnls < 0, sim_pnls, 0)).sum(axis=1)
    pf_sim = np.where(gross_loss > 0, gross_win / gross_loss, 2.0)

    return {
        "n_trades": n,
        "n_simulations": n_sims,
        "net_pnl": {
            "p5":  round(float(np.percentile(final, 5)), 1),
            "p25": round(float(np.percentile(final, 25)), 1),
            "median": round(float(np.median(final)), 1),
            "p75": round(float(np.percentile(final, 75)), 1),
            "p95": round(float(np.percentile(final, 95)), 1),
        },
        "max_drawdown": {
            "p50": round(float(np.percentile(max_dd_abs, 50)), 4),
            "p90": round(float(np.percentile(max_dd_abs, 90)), 4),
            "p95": round(float(np.percentile(max_dd_abs, 95)), 4),
        },
        "profit_factor": {
            "p25": round(float(np.percentile(pf_sim, 25)), 3),
            "median": round(float(np.median(pf_sim)), 3),
            "p75": round(float(np.percentile(pf_sim, 75)), 3),
        },
        "prob_positive": round(float((final > 0).mean()), 3),
        "prob_ruin_10pct": round(float((max_dd_abs > 0.10).mean()), 4),
        "prob_ruin_5pct": round(float((max_dd_abs > 0.05).mean()), 4),
    }


# ── Runner principal ──────────────────────────────────────────────────────────

def run_validation(
    symbol: str,
    strategy: str,
    timeframe: str,
    start: str,
    end: str,
    risk: float = 0.004,
    adx_min: float | None = None,
    rr_target: float | None = None,
    is_months: int = 12,
    oos_months: int = 6,
    step_months: int = 6,
    n_mc: int = 5000,
    initial_balance: float = 10000.0,
    rsi_oversold: float | None = None,
    rsi_overbought: float | None = None,
    bb_std: float | None = None,
    exit_mode: str = "fixed",
    trail_atr_mult: float = 1.0,
    long_only: bool = False,
) -> dict:
    setup_logging()

    is_combined = strategy == _COMBINED_STRATEGY
    tf_label = "15m+1h" if is_combined else timeframe

    total_months = _months_between(start, end)
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD VALIDATION — {symbol} {strategy} {tf_label}")
    print(f"Periodo: {start} → {end} ({total_months} meses)")
    print(f"IS={is_months}m  OOS={oos_months}m  Step={step_months}m")
    print(f"Risk={risk*100:.1f}%  ADX>{adx_min or 25}  RR={rr_target or 2.5}")
    print(f"{'='*60}\n")

    windows = _build_windows(start, end, is_months, oos_months, step_months)
    if not windows:
        raise ValueError(f"Rango insuficiente para {is_months}m IS + {oos_months}m OOS")

    # Seleccionar función de backtest según estrategia
    if is_combined:
        from src.orchestration.run_combined import run_combined_backtest
        def _run(start, end):
            return run_combined_backtest(
                symbol=symbol, start=start, end=end,
                initial_balance=initial_balance, risk_pct=risk,
                adx_min=adx_min or 25.0, rr_target=rr_target or 2.5,
                research=True, daily_trend=True,
            )
    else:
        bt_kwargs = dict(
            symbol=symbol, strategy=strategy, timeframe=timeframe,
            initial_balance=initial_balance, risk_pct=risk,
            research=True, adx_min=adx_min, rr_target=rr_target,
            rsi_oversold=rsi_oversold, rsi_overbought=rsi_overbought,
            bb_std=bb_std, exit_mode=exit_mode, trail_atr_mult=trail_atr_mult,
            long_only=long_only,
        )
        def _run(start, end):
            return run_backtest(start=start, end=end, **bt_kwargs)

    rows = []
    all_oos_pnls: list[float] = []

    for i, w in enumerate(windows, 1):
        print(f"[W{i}] IS {w['is_start']}→{w['is_end']}  |  OOS {w['oos_start']}→{w['oos_end']}")

        is_res  = _run(w["is_start"],  w["is_end"])
        oos_res = _run(w["oos_start"], w["oos_end"])

        is_pf  = _pf(is_res)
        oos_pf = _pf(oos_res)
        wfe    = walk_forward_efficiency(is_pf, oos_pf)  # None when IS PF ≤ 1.0

        # Acumular trade PnLs OOS para Monte Carlo (directamente del resultado)
        all_oos_pnls.extend(oos_res.get("trade_pnls", []))

        wfe_str = f"{wfe:.3f}" if wfe is not None else "n/a (IS perdedor)"
        wfe_ok  = wfe is not None and wfe >= 0.5

        row = {
            "window": f"W{i}",
            "is_period": f"{w['is_start']}→{w['is_end']}",
            "oos_period": f"{w['oos_start']}→{w['oos_end']}",
            "is_trades": _trades(is_res),
            "is_wr": round(_wr(is_res), 3),
            "is_pf": round(is_pf, 3),
            "is_pnl": round(_net(is_res), 1),
            "is_dd": round(_dd(is_res), 3),
            "oos_trades": _trades(oos_res),
            "oos_wr": round(_wr(oos_res), 3),
            "oos_pf": round(oos_pf, 3),
            "oos_pnl": round(_net(oos_res), 1),
            "oos_dd": round(_dd(oos_res), 3),
            "wfe": wfe,
        }
        rows.append(row)

        status = "✓" if oos_pf >= 1.0 else "✗"
        if is_combined:
            print(f"     IS  → PF {is_pf:.3f} | WR {_wr(is_res):.1%} | PnL ${_net(is_res):+.0f} | DD {_dd(is_res):.1%} | trades {_trades(is_res)} (bo={is_res.get('bo_signals',0)} pb={is_res.get('pb_signals',0)})")
            print(f"     OOS → PF {oos_pf:.3f} | WR {_wr(oos_res):.1%} | PnL ${_net(oos_res):+.0f} | DD {_dd(oos_res):.1%} | trades {_trades(oos_res)} (bo={oos_res.get('bo_signals',0)} pb={oos_res.get('pb_signals',0)})  {status}")
        else:
            print(f"     IS  → PF {is_pf:.3f} | WR {_wr(is_res):.1%} | PnL ${_net(is_res):+.0f} | DD {_dd(is_res):.1%}")
            print(f"     OOS → PF {oos_pf:.3f} | WR {_wr(oos_res):.1%} | PnL ${_net(oos_res):+.0f} | DD {_dd(oos_res):.1%}  {status}")
        print(f"     WFE = {wfe_str}  ({'PASS ≥0.5' if wfe_ok else ('FAIL <0.5' if wfe is not None else 'N/A')})\n")

    df = pd.DataFrame(rows)

    # Resumen walk-forward — WFE solo sobre ventanas con IS PF > 1.0
    oos_pass  = (df["oos_pf"] >= 1.0).sum()
    avg_oos_pf = df["oos_pf"].mean()
    valid_wfe = [r["wfe"] for r in rows if r["wfe"] is not None]
    avg_wfe   = sum(valid_wfe) / len(valid_wfe) if valid_wfe else float("nan")

    print(f"{'─'*60}")
    print(f"RESUMEN WALK-FORWARD ({len(windows)} ventanas)")
    n_wfe_valid = len(valid_wfe)
    print(f"  OOS windows rentables : {oos_pass}/{len(windows)}")
    print(f"  PF medio OOS          : {avg_oos_pf:.3f}")
    if valid_wfe:
        print(f"  WFE medio             : {avg_wfe:.3f}  (sobre {n_wfe_valid} ventanas con IS PF>1.0; objetivo ≥ 0.5)")
    else:
        print(f"  WFE medio             : n/a (todas las ventanas IS tuvieron PF ≤ 1.0)")

    # Monte Carlo
    print(f"\n{'─'*60}")
    if all_oos_pnls:
        print(f"MONTE CARLO — {len(all_oos_pnls)} trades OOS ({n_mc:,} simulaciones)")
        mc = monte_carlo_pnl(all_oos_pnls, initial_balance=initial_balance, n_sims=n_mc)
        print(f"  PnL neto  p5/median/p95 : ${mc['net_pnl']['p5']:+.0f} / ${mc['net_pnl']['median']:+.0f} / ${mc['net_pnl']['p95']:+.0f}")
        print(f"  Max DD    p50/p90/p95   : {mc['max_drawdown']['p50']:.1%} / {mc['max_drawdown']['p90']:.1%} / {mc['max_drawdown']['p95']:.1%}  (peor caso)")
        print(f"  PF        p25/med/p75   : {mc['profit_factor']['p25']:.3f} / {mc['profit_factor']['median']:.3f} / {mc['profit_factor']['p75']:.3f}")
        print(f"  P(positivo)             : {mc['prob_positive']:.1%}")
        print(f"  P(ruin DD>10%)          : {mc['prob_ruin_10pct']:.1%}")
        print(f"  P(ruin DD>5%)           : {mc['prob_ruin_5pct']:.1%}")
    else:
        mc = {}
        print("  [!] No se encontraron trade logs OOS para Monte Carlo")

    # Veredicto — primario: OOS pass rate + avg OOS PF; secundario: WFE si disponible
    oos_pass_rate = oos_pass / len(windows)
    # WFE solo penaliza si hay suficientes ventanas válidas (≥2) y el promedio es negativo
    wfe_penalty = len(valid_wfe) >= 2 and avg_wfe < 0.0

    print(f"\n{'='*60}")
    if oos_pass_rate >= 0.5 and avg_oos_pf >= 1.3 and not wfe_penalty:
        if avg_oos_pf >= 1.5:
            verdict = "ESTRATEGIA ROBUSTA — edge real, apta para live con gestión de régimen"
        else:
            verdict = "ESTRATEGIA MARGINAL — edge presente pero delgado, requiere confirmación"
    elif oos_pass_rate >= 0.5 and wfe_penalty:
        verdict = "EDGE DEPENDIENTE DE RÉGIMEN — rentable en tendencia, revisar filtros macro"
    else:
        verdict = "EDGE INESTABLE — no apta para live trading sin mejoras adicionales"
    print(f"VEREDICTO: {verdict}")
    print(f"  OOS pass rate: {oos_pass_rate:.0%}  |  PF OOS medio: {avg_oos_pf:.3f}")
    if valid_wfe:
        print(f"  WFE ({n_wfe_valid} ventanas válidas): {avg_wfe:.3f}")
    print(f"{'='*60}\n")

    # Guardar resultados
    out = {
        "config": {
            "symbol": symbol, "strategy": strategy, "timeframe": timeframe,
            "is_months": is_months, "oos_months": oos_months,
            "risk": risk, "adx_min": adx_min, "rr_target": rr_target,
        },
        "windows": rows,
        "summary": {
            "oos_pass": int(oos_pass),
            "total_windows": len(windows),
            "oos_pass_rate": round(oos_pass_rate, 3),
            "avg_oos_pf": round(avg_oos_pf, 3),
            "avg_wfe": round(avg_wfe, 3) if valid_wfe else None,
            "verdict": verdict,
        },
        "monte_carlo": mc,
    }

    tf_tag = "15m+1h" if is_combined else timeframe
    out_path = Path("reports/strategy_reports") / f"{symbol}_{strategy}_{tf_tag}_validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"[report] Guardado en {out_path}")

    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk-forward + Monte Carlo validation")
    parser.add_argument("--symbol",    default="XAUUSD")
    parser.add_argument("--strategy",  default="pullback", choices=["breakout", "pullback", "combined", "mean_reversion", "fvg", "ny_breakout", "asian_orb"])
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--start",     default="2022-01-01")
    parser.add_argument("--end",       default="2025-01-01")
    parser.add_argument("--risk",      type=float, default=0.004)
    parser.add_argument("--adx-min",   type=float, default=25.0)
    parser.add_argument("--rr-target", type=float, default=2.5)
    parser.add_argument("--is-months", type=int,   default=12)
    parser.add_argument("--oos-months",type=int,   default=6)
    parser.add_argument("--step",      type=int,   default=6)
    parser.add_argument("--mc-sims",   type=int,   default=5000)
    parser.add_argument("--exit-mode", default="fixed", choices=["fixed", "partial", "trail"])
    parser.add_argument("--trail-atr-mult", type=float, default=1.0)
    parser.add_argument("--long-only", action="store_true", help="Solo señales LONG (pullback strategy)")
    args = parser.parse_args()

    run_validation(
        symbol=args.symbol, strategy=args.strategy, timeframe=args.timeframe,
        start=args.start, end=args.end, risk=args.risk,
        adx_min=args.adx_min, rr_target=args.rr_target,
        is_months=args.is_months, oos_months=args.oos_months, step_months=args.step,
        n_mc=args.mc_sims, exit_mode=args.exit_mode, trail_atr_mult=args.trail_atr_mult,
        long_only=args.long_only,
    )
