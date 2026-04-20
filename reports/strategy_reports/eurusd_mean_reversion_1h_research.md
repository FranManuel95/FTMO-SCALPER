# Research Report: EURUSD Mean Reversion 1h
Generated: 2026-04-20 14:23

## Hipótesis
EURUSD pasa gran parte del tiempo en rangos. Cuando el precio se aleja significativamente de su media (Bollinger Band exterior) en un contexto de mercado lateral (ADX bajo), tiende a revertir. El filtro ADX<25 asegura que solo operamos en rango, evitando breakouts tendenciales que destruyen la estrategia.

## Configuración
- Símbolo   : `EURUSD`
- Estrategia: `mean_reversion` en `1h`
- ADX mín   : —
- RR target : 1.5
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2023-01-01`
  PF     : 0.888  ✗  (mín 1.2)
  WR     : 27.5%
  Trades : 40       ✓  (mín 30)
  DD     : 1.4%  ✓  (máx 10%)
  PnL    : $-129  (-1.3%)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
