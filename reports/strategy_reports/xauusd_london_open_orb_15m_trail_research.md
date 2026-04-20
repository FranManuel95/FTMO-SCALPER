# Research Report: XAUUSD London Open ORB 15m Trail
Generated: 2026-04-20 17:56

## Hipótesis
Revisita London ORB frozen (IS PF=1.017 con fixed TP). El NY ORB tenia PF=1.345 con fixed y paso a 4.205 con trail=0.5. El London ORB falla porque los breakouts son falsos y revierten — exactamente el caso donde el trail convierte -1R en +0.3R. Hipotesis: trail rescata la estrategia igual que hizo con NY ORB.

## Configuración
- Símbolo   : `XAUUSD`
- Estrategia: `london_open` en `15m`
- ADX mín   : 18
- RR target : 2.5
- Risk/trade: 0.25%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 2.792  ✓  (mín 1.2)
  WR     : 54.6%
  Trades : 491       ✓  (mín 30)
  DD     : 0.1%  ✓  (máx 10%)
  PnL    : $+1020  (+10.2%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 2.455  ✓  (mín 1.1)
  WR     : 49.3%
  Trades : 209       ✓  (mín 30)
  DD     : 0.0%  ✓  (máx 10%)
  PnL    : $+372  (+3.7%)

### Comparativa IS → OOS
  PF IS → OOS : 2.792 → 2.455
  Degradación : 12%  ✓  (máx 35%)
  Ratio OOS/IS: 0.88  (edge estable)

**Status: PASS ✓**

## Gate 3 — Walk-Forward + Monte Carlo
Período: `2022-01-01` → `2026-04-01`
  OOS pass rate    : 100%  ✓
  Avg OOS PF       : 2.907
  P(profit) MC     : 100.0%
  P(ruin DD>10%) MC: 0.0%  ✓
  Max DD p95 MC    : 0.5%
  Sistema veredicto: ESTRATEGIA ROBUSTA — edge real, apta para live con gestión de régimen

**Status: PASS ✓**

## Veredicto Final
**PASS — ESTRATEGIA ROBUSTA | OOS 100% profitable | PF 2.907 | P(profit) 100.0%**
