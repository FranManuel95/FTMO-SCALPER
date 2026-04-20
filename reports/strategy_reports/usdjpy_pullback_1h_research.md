# Research Report: USDJPY Pullback 1h
Generated: 2026-04-20 16:06

## Hipótesis
USDJPY tuvo tendencia fuerte 2022-2024 (yen debil por divergencia Fed/BoJ). Pullback sobre EMA20 en tendencia con ADX>20. Umbral ADX menor que XAUUSD porque los cruces JPY tienen menor ADX medio pero movimientos direccionales claros. Riesgo macro: BoJ subidas de tipos pueden revertir el yen bruscamente.

## Configuración
- Símbolo   : `USDJPY`
- Estrategia: `pullback` en `1h`
- ADX mín   : 20
- RR target : 2.5
- Risk/trade: 0.30%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.284  ✓  (mín 1.2)
  WR     : 33.9%
  Trades : 224       ✓  (mín 30)
  DD     : 0.6%  ✓  (máx 10%)
  PnL    : $+1260  (+12.6%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 1.562  ✓  (mín 1.1)
  WR     : 38.5%
  Trades : 78       ✓  (mín 30)
  DD     : 0.3%  ✓  (máx 10%)
  PnL    : $+810  (+8.1%)

### Comparativa IS → OOS
  PF IS → OOS : 1.284 → 1.562
  Degradación : -22%  ✓  (máx 35%)
  Ratio OOS/IS: 1.22  (edge estable)

**Status: PASS ✓**

## Gate 3 — Walk-Forward + Monte Carlo
Período: `2022-01-01` → `2026-04-01`
  OOS pass rate    : 100%  ✓
  Avg OOS PF       : 1.362
  P(profit) MC     : 96.5%
  P(ruin DD>10%) MC: 1.8%  ✓
  Max DD p95 MC    : 8.2%
  Sistema veredicto: ESTRATEGIA MARGINAL — edge presente pero delgado, requiere confirmación

**Status: PASS ✓**

## Veredicto Final
**CONDITIONAL — Edge presente pero delgado | OOS 100% | PF 1.362**
