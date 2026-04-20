# Research Report: XAUUSD Pullback 1h
Generated: 2026-04-20 15:59

## Hipótesis
XAUUSD tiene tendencia secular alcista. Pullback sobre EMA20 en estructura alcista (EMA20>EMA50) con ADX>25 y filtro H4 trend. Edge robusto confirmado en 4+ anhos de datos (2022-2026) incluyendo el regimen de alza de tipos 2022.

## Configuración
- Símbolo   : `XAUUSD`
- Estrategia: `pullback` en `1h`
- ADX mín   : 25
- RR target : 2.5
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.261  ✓  (mín 1.2)
  WR     : 33.5%
  Trades : 170       ✓  (mín 30)
  DD     : 6.4%  ✓  (máx 10%)
  PnL    : $+1180  (+11.8%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 1.987  ✓  (mín 1.1)
  WR     : 44.3%
  Trades : 70       ✓  (mín 30)
  DD     : 0.4%  ✓  (máx 10%)
  PnL    : $+1540  (+15.4%)

### Comparativa IS → OOS
  PF IS → OOS : 1.261 → 1.987
  Degradación : -58%  ✓  (máx 35%)
  Ratio OOS/IS: 1.58  (edge estable)

**Status: PASS ✓**

## Gate 3 — Walk-Forward + Monte Carlo
Período: `2022-01-01` → `2026-04-01`
  OOS pass rate    : 83%  ✓
  Avg OOS PF       : 1.905
  P(profit) MC     : 99.8%
  P(ruin DD>10%) MC: 0.5%  ✓
  Max DD p95 MC    : 7.0%
  Sistema veredicto: ESTRATEGIA ROBUSTA — edge real, apta para live con gestión de régimen

**Status: PASS ✓**

## Veredicto Final
**PASS — ESTRATEGIA ROBUSTA | OOS 83% profitable | PF 1.905 | P(profit) 99.8%**
