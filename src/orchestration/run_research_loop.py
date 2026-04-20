"""
Pipeline de investigación automatizado — aplica todas las skills de forma secuencial.

Carga una spec YAML de config/strategies/, ejecuta tres gates (IS → OOS → Walk-Forward)
con criterios de aceptación automáticos y genera un reporte markdown con veredicto.

Uso:
  python -m src.orchestration.run_research_loop --spec config/strategies/eurusd_pullback_1h.yaml
  python -m src.orchestration.run_research_loop --spec config/strategies/eurusd_pullback_1h.yaml --force-wf

Gates automáticos:
  Gate 1 — IS:   PF >= min_pf_is AND trades >= min_trades AND DD <= max_dd
  Gate 2 — OOS:  PF >= min_pf_oos AND degradación IS→OOS <= max_degradation
  Gate 3 — WF:   OOS pass rate >= 50% AND P(DD>10%) <= 15%
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.core.logging import setup_logging
from src.orchestration.run_backtest import run_backtest
from src.orchestration.run_validation import monte_carlo_pnl, run_validation


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_spec(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _pf(res: dict) -> float:
    return res["performance"]["profit_factor"]

def _dd(res: dict) -> float:
    return res["ftmo_checks"]["max_loss_check"]["max_drawdown_pct"]

def _trades(res: dict) -> int:
    return res["performance"]["total_trades"]

def _wr(res: dict) -> float:
    return res["performance"]["win_rate"]

def _net(res: dict) -> float:
    return res["performance"]["net_pnl"]

def _pct(res: dict) -> float:
    return res["performance"]["net_pnl_pct"]


def _icon(ok: bool) -> str:
    return "✓" if ok else "✗"


# ── Review automático (skill review_backtest_results) ─────────────────────────

def _review_single(res: dict, label: str, gates: dict) -> tuple[bool, list[str]]:
    """Aplica la lógica de review_backtest_results. Retorna (passed, [mensajes])."""
    pf = _pf(res)
    dd = _dd(res)
    n  = _trades(res)
    wr = _wr(res)
    msgs = []
    flags = []

    # Red flags automáticos (skill: review_backtest_results)
    if pf > 3.0 and n < 50:
        flags.append(f"  ⚠ PF muy alto ({pf:.2f}) con pocos trades ({n}) — posible overfitting")
    if wr > 0.70 and res["performance"].get("expectancy", 0) < 0:
        flags.append(f"  ⚠ WR muy alta ({wr:.0%}) pero expectancy negativa — frágil")
    if dd > 0.08:
        flags.append(f"  ⚠ DD {dd:.1%} > 8% — peligroso para FTMO (límite 10%)")
    if n < 30:
        flags.append(f"  ⚠ Solo {n} trades — insuficiente para significancia estadística")

    # Checks de gate
    pf_ok = pf >= gates["min_pf_is"] if label == "IS" else pf >= gates["min_pf_oos"]
    dd_ok = dd <= gates["max_dd_pct"]
    n_ok  = n  >= gates["min_trades"]

    msgs.append(f"  PF     : {pf:.3f}  {_icon(pf_ok)}  (mín {gates['min_pf_is'] if label == 'IS' else gates['min_pf_oos']:.1f})")
    msgs.append(f"  WR     : {wr:.1%}")
    msgs.append(f"  Trades : {n}       {_icon(n_ok)}  (mín {gates['min_trades']})")
    msgs.append(f"  DD     : {dd:.1%}  {_icon(dd_ok)}  (máx {gates['max_dd_pct']:.0%})")
    msgs.append(f"  PnL    : ${_net(res):+.0f}  ({_pct(res):+.1%})")

    passed = pf_ok and dd_ok and n_ok
    return passed, msgs + flags


def _review_degradation(is_res: dict, oos_res: dict, gates: dict) -> tuple[bool, list[str]]:
    """Compara IS vs OOS (skill: compare_experiments)."""
    is_pf  = _pf(is_res)
    oos_pf = _pf(oos_res)
    deg = (is_pf - oos_pf) / is_pf if is_pf > 0 else 1.0
    deg_ok = deg <= gates["max_is_oos_degradation"]
    ratio = oos_pf / is_pf if is_pf > 0 else 0

    msgs = [
        f"  PF IS → OOS : {is_pf:.3f} → {oos_pf:.3f}",
        f"  Degradación : {deg:.0%}  {_icon(deg_ok)}  (máx {gates['max_is_oos_degradation']:.0%})",
        f"  Ratio OOS/IS: {ratio:.2f}  {'(edge estable)' if ratio >= 0.70 else '(edge se deteriora)'}"
    ]
    return deg_ok, msgs


# ── Generador de reporte markdown ─────────────────────────────────────────────

def _build_report(spec: dict, gates: dict, sections: list[str], verdict: str) -> str:
    lines = [
        f"# Research Report: {spec['name']}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Hipótesis",
        spec.get("hypothesis", "—").strip(),
        "",
        "## Configuración",
        f"- Símbolo   : `{spec['symbol']}`",
        f"- Estrategia: `{spec['strategy']}` en `{spec['timeframe']}`",
        f"- ADX mín   : {spec['params'].get('adx_min', '—')}",
        f"- RR target : {spec['params'].get('rr_target', '—')}",
        f"- Risk/trade: {spec['params'].get('risk_pct', 0)*100:.2f}%",
        "",
    ]
    lines += sections
    lines += ["", f"## Veredicto Final", f"**{verdict}**", ""]
    return "\n".join(lines)


# ── Pipeline principal ─────────────────────────────────────────────────────────

def run_research_loop(spec_path: str, force_wf: bool = False) -> dict:
    setup_logging()
    spec  = _load_spec(spec_path)
    gates = spec["gates"]
    p     = spec["params"]
    per   = spec["periods"]

    symbol    = spec["symbol"]
    strategy  = spec["strategy"]
    timeframe = spec["timeframe"]
    risk      = p["risk_pct"]
    adx_min   = p.get("adx_min")
    rr_target = p.get("rr_target")

    bt_kwargs = dict(
        symbol=symbol, strategy=strategy, timeframe=timeframe,
        initial_balance=10000.0, risk_pct=risk,
        research=True, adx_min=adx_min, rr_target=rr_target,
    )

    sections = []
    verdict  = ""
    status   = "FAIL"

    # ── GATE 1: In-Sample ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"RESEARCH LOOP — {spec['name']}")
    print(f"{'='*60}")
    print(f"\n[Gate 1] In-Sample: {per['is_start']} → {per['is_end']}")

    is_res = run_backtest(start=per["is_start"], end=per["is_end"], **bt_kwargs)
    is_passed, is_msgs = _review_single(is_res, "IS", gates)

    sections.append("## Gate 1 — In-Sample")
    sections.append(f"Período: `{per['is_start']}` → `{per['is_end']}`")
    sections += is_msgs

    for m in is_msgs:
        print(m)

    if not is_passed:
        verdict = "FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra"
        sections.append(f"\n**Status: FAIL ✗** — pipeline detenido")
        print(f"\n  → FAIL Gate 1. Deteniendo pipeline.")
        _save(spec, sections, verdict, status)
        return {"verdict": verdict, "gate_failed": 1, "is": is_res}

    sections.append(f"\n**Status: PASS ✓**")
    print(f"\n  → PASS Gate 1 ✓")

    # ── GATE 2: Out-of-Sample + Degradación ──────────────────────────────────
    print(f"\n[Gate 2] Out-of-Sample: {per['oos_start']} → {per['oos_end']}")

    oos_res = run_backtest(start=per["oos_start"], end=per["oos_end"], **bt_kwargs)
    oos_passed, oos_msgs = _review_single(oos_res, "OOS", gates)
    deg_passed, deg_msgs = _review_degradation(is_res, oos_res, gates)

    sections.append("\n## Gate 2 — Out-of-Sample")
    sections.append(f"Período: `{per['oos_start']}` → `{per['oos_end']}`")
    sections += oos_msgs
    sections.append("\n### Comparativa IS → OOS")
    sections += deg_msgs

    for m in oos_msgs + deg_msgs:
        print(m)

    gate2_ok = oos_passed and deg_passed
    if not gate2_ok:
        verdict = "FAIL en Gate 2 (OOS) — edge no se mantiene fuera de muestra"
        sections.append(f"\n**Status: FAIL ✗** — pipeline detenido")
        print(f"\n  → FAIL Gate 2. Deteniendo pipeline.")
        _save(spec, sections, verdict, status)
        return {"verdict": verdict, "gate_failed": 2, "is": is_res, "oos": oos_res}

    sections.append(f"\n**Status: PASS ✓**")
    print(f"\n  → PASS Gate 2 ✓")

    # ── GATE 3: Walk-Forward + Monte Carlo ────────────────────────────────────
    print(f"\n[Gate 3] Walk-Forward: {per['wf_start']} → {per['wf_end']}")

    wf_res = run_validation(
        symbol=symbol, strategy=strategy, timeframe=timeframe,
        start=per["wf_start"], end=per["wf_end"],
        risk=risk, adx_min=adx_min, rr_target=rr_target,
        n_mc=5000, initial_balance=10000.0,
    )

    wf_sum = wf_res["summary"]
    mc     = wf_res.get("monte_carlo", {})

    pass_rate = wf_sum["oos_pass_rate"]
    avg_pf    = wf_sum["avg_oos_pf"]
    mc_ruin   = mc.get("prob_ruin_10pct", 1.0) if mc else 1.0
    mc_prob   = mc.get("prob_positive", 0.0) if mc else 0.0
    wf_verdict = wf_sum.get("verdict", "—")

    wf_ok     = pass_rate >= 0.5 and mc_ruin <= 0.15

    sections.append("\n## Gate 3 — Walk-Forward + Monte Carlo")
    sections.append(f"Período: `{per['wf_start']}` → `{per['wf_end']}`")
    sections.append(f"  OOS pass rate    : {pass_rate:.0%}  {_icon(pass_rate >= 0.5)}")
    sections.append(f"  Avg OOS PF       : {avg_pf:.3f}")
    if mc:
        sections.append(f"  P(profit) MC     : {mc_prob:.1%}")
        sections.append(f"  P(ruin DD>10%) MC: {mc_ruin:.1%}  {_icon(mc_ruin <= 0.15)}")
        dd_p95 = mc.get('max_drawdown', {}).get('p95', 0)
        sections.append(f"  Max DD p95 MC    : {dd_p95:.1%}")
    sections.append(f"  Sistema veredicto: {wf_verdict}")

    if not wf_ok:
        verdict = f"FAIL en Gate 3 (WF) — pass rate {pass_rate:.0%} o P(ruin) {mc_ruin:.1%} fuera de límites"
        sections.append(f"\n**Status: FAIL ✗**")
        print(f"\n  → FAIL Gate 3.")
        status = "FAIL"
    else:
        status = "PASS"
        if avg_pf >= 1.5 and mc_prob >= 0.85:
            verdict = f"PASS — ESTRATEGIA ROBUSTA | OOS {pass_rate:.0%} profitable | PF {avg_pf:.3f} | P(profit) {mc_prob:.1%}"
        else:
            verdict = f"CONDITIONAL — Edge presente pero delgado | OOS {pass_rate:.0%} | PF {avg_pf:.3f}"
        sections.append(f"\n**Status: {status} {'✓' if status == 'PASS' else '~'}**")
        print(f"\n  → {status} Gate 3 ✓")

    _save(spec, sections, verdict, status)
    print(f"\n{'='*60}")
    print(f"VEREDICTO: {verdict}")
    print(f"{'='*60}\n")

    return {
        "verdict": verdict,
        "status": status,
        "is": is_res,
        "oos": oos_res,
        "walk_forward": wf_res,
    }


def _save(spec: dict, sections: list[str], verdict: str, status: str):
    report_text = _build_report(spec, spec["gates"], sections, verdict)
    slug = spec["name"].lower().replace(" ", "_").replace("/", "")
    out_dir = Path("reports/strategy_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{slug}_research.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # Actualizar status y verdict en el YAML de spec
    spec_path_candidates = list(Path("config/strategies").glob("*.yaml"))
    for sp in spec_path_candidates:
        with open(sp) as f:
            data = yaml.safe_load(f)
        if data.get("name") == spec["name"]:
            data["status"] = "validated" if status == "PASS" else ("in_research" if status == "CONDITIONAL" else "frozen")
            data["verdict"] = verdict
            with open(sp, "w") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            break

    print(f"\n[report] Guardado en {md_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Research Loop — IS → OOS → Walk-Forward")
    parser.add_argument("--spec",     required=True, help="Path al YAML de estrategia (config/strategies/*.yaml)")
    parser.add_argument("--force-wf", action="store_true", help="Forzar walk-forward aunque fallen gates anteriores")
    args = parser.parse_args()

    run_research_loop(args.spec, force_wf=args.force_wf)
