# Research Report: GBPJPY Pullback 1h
Generated: 2026-04-20 16:07

## Hipótesis
GBPJPY es el par JPY cruzado mas volatil (apodado "la bestia"). Tendencia alcista fuerte 2022-2024: GBP se recupero post-Brexit + JPY debil por BoJ. ADX>22 para filtrar tendencia. Riesgo: reversiones brutales del yen en eventos BoJ, gap risk elevado. Se usa riesgo conservador 0.3% dado el DD potencial.

## Configuración
- Símbolo   : `GBPJPY`
- Estrategia: `pullback` en `1h`
- ADX mín   : 22
- RR target : 2.5
- Risk/trade: 0.30%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.208  ✓  (mín 1.2)
  WR     : 32.6%
  Trades : 178       ✓  (mín 30)
  DD     : 0.8%  ✓  (máx 10%)
  PnL    : $+750  (+7.5%)

**Status: PASS ✓**

## Gate 2 — Out-of-Sample
Período: `2025-01-01` → `2026-04-01`
  PF     : 0.990  ✗  (mín 1.1)
  WR     : 28.4%
  Trades : 67       ✓  (mín 30)
  DD     : 2.9%  ✓  (máx 10%)
  PnL    : $-15  (-0.1%)

### Comparativa IS → OOS
  PF IS → OOS : 1.208 → 0.990
  Degradación : 18%  ✓  (máx 35%)
  Ratio OOS/IS: 0.82  (edge estable)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 2 (OOS) — edge no se mantiene fuera de muestra**
