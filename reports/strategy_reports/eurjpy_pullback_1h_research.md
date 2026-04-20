# Research Report: EURJPY Pullback 1h
Generated: 2026-04-20 16:07

## Hipótesis
EURJPY combina dos drivers direccionales: EUR alcista (macro Europa post-COVID) + JPY debil (BoJ sin subir tipos hasta 2024). La tendencia 2022-2024 fue mas fuerte que USDJPY porque ambas monedas se movian en la misma direccion. Pullback EMA20 en estructura alcista con ADX>22. Riesgo: posibles reversiones brutas del yen en noticias BoJ.

## Configuración
- Símbolo   : `EURJPY`
- Estrategia: `pullback` en `1h`
- ADX mín   : 22
- RR target : 2.5
- Risk/trade: 0.30%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.004  ✗  (mín 1.2)
  WR     : 28.6%
  Trades : 178       ✓  (mín 30)
  DD     : 1.2%  ✓  (máx 10%)
  PnL    : $+15  (+0.1%)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
