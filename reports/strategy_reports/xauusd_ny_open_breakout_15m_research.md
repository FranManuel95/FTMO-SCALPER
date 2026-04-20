# Research Report: XAUUSD NY Open Breakout 15m
Generated: 2026-04-20 16:33

## Hipótesis
El NY Open (13:30 UTC = 15:30 broker) es el punto de mayor liquidez para XAUUSD: London+NY se solapan y el mercado de futuros de CME inicia. Se construye el rango de la primera hora de apertura NY (15:00-16:00 broker), luego se opera el breakout en direccion del trend H4. A diferencia del London Breakout (rango asiatico 7h), este rango es mas compacto y el momento del breakout coincide con el mayor volumen institucional. Sin dependencia de regimen: funciona en bull y en laterales porque captura el momentum de sesion NY independientemente del trend macro.

## Configuración
- Símbolo   : `XAUUSD`
- Estrategia: `ny_breakout` en `15m`
- ADX mín   : 18
- RR target : 2.5
- Risk/trade: 0.25%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.350  ✓  (mín 1.2)
  WR     : 35.1%
  Trades : 499       ✓  (mín 30)
  DD     : 2.4%  ✓  (máx 10%)
  PnL    : $+2838  (+28.4%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 1.421  ✓  (mín 1.1)
  WR     : 36.2%
  Trades : 218       ✓  (mín 30)
  DD     : 2.0%  ✓  (máx 10%)
  PnL    : $+1462  (+14.6%)

### Comparativa IS → OOS
  PF IS → OOS : 1.350 → 1.421
  Degradación : -5%  ✓  (máx 35%)
  Ratio OOS/IS: 1.05  (edge estable)

**Status: PASS ✓**

## Gate 3 — Walk-Forward + Monte Carlo
Período: `2022-01-01` → `2026-04-01`
  OOS pass rate    : 83%  ✓
  Avg OOS PF       : 1.345
  P(profit) MC     : 99.7%
  P(ruin DD>10%) MC: 1.8%  ✓
  Max DD p95 MC    : 8.6%
  Sistema veredicto: ESTRATEGIA MARGINAL — edge presente pero delgado, requiere confirmación

**Status: PASS ✓**

## Veredicto Final
**CONDITIONAL — Edge presente pero delgado | OOS 83% | PF 1.345**
