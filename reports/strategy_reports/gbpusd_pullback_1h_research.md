# Research Report: GBPUSD Pullback 1H
Generated: 2026-04-20 17:55

## Hipótesis
GBP tiene driver macro fuerte y unidireccional (BoE vs Fed). Divergencia de tipos: Fed subio agresivamente en 2022-2023, BoE siguio pero con lag. En 2024-2025 la Fed empieza a bajar mientras BoE mantiene higher-for-longer. Pullback sobre EMA20 en estructura alcista con ADX>25 y filtro H4 trend. Trailing stop 0.5xATR desde el inicio del spec.

## Configuración
- Símbolo   : `GBPUSD`
- Estrategia: `pullback` en `1h`
- ADX mín   : 25
- RR target : 2.5
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.860  ✓  (mín 1.2)
  WR     : 56.2%
  Trades : 153       ✓  (mín 30)
  DD     : 0.1%  ✓  (máx 10%)
  PnL    : $+750  (+7.5%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 2.938  ✓  (mín 1.1)
  WR     : 63.0%
  Trades : 54       ✓  (mín 30)
  DD     : 0.2%  ✓  (máx 10%)
  PnL    : $+552  (+5.5%)

### Comparativa IS → OOS
  PF IS → OOS : 1.860 → 2.938
  Degradación : -58%  ✓  (máx 35%)
  Ratio OOS/IS: 1.58  (edge estable)

**Status: PASS ✓**

## Gate 3 — Walk-Forward + Monte Carlo
Período: `2022-01-01` → `2026-04-01`
  OOS pass rate    : 100%  ✓
  Avg OOS PF       : 2.817
  P(profit) MC     : 100.0%
  P(ruin DD>10%) MC: 0.0%  ✓
  Max DD p95 MC    : 1.9%
  Sistema veredicto: ESTRATEGIA ROBUSTA — edge real, apta para live con gestión de régimen

**Status: PASS ✓**

## Veredicto Final
**PASS — ESTRATEGIA ROBUSTA | OOS 100% profitable | PF 2.817 | P(profit) 100.0%**
