# Research Report: EURGBP Mean Reversion 1h
Generated: 2026-04-20 16:08

## Hipótesis
EURGBP es el par mas range-bound del forex: EUR y GBP son dos monedas europeas altamente correladas que tienden a oscilar en rangos estrechos. Con ADX<22 (filtro tendencia), el precio rebota en las BB exteriores con alta probabilidad. El evento Liz Truss (Sep 2022) sera filtrado por ADX alto. Hipotesis: MR funciona mejor en EURGBP que en EURUSD porque el par no tiene drivers macro unidireccionales de largo plazo.

## Configuración
- Símbolo   : `EURGBP`
- Estrategia: `mean_reversion` en `1h`
- ADX mín   : —
- RR target : 1.5
- Risk/trade: 0.30%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2024-01-01`
  PF     : 1.160  ✗  (mín 1.2)
  WR     : 27.7%
  Trades : 112       ✓  (mín 30)
  DD     : 1.2%  ✓  (máx 10%)
  PnL    : $+389  (+3.9%)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
