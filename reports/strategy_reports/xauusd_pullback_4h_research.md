# Research Report: XAUUSD Pullback 4H
Generated: 2026-04-20 17:55

## Hipótesis
Mismo pullback EMA20 que en 1H pero en 4H. Senales mas limpias, menos ruido, ATR ~$25-35 da mas margen al trail. Menos trades (~1-2/semana) pero mayor fiabilidad esperada. El trailing stop 0.5xATR sigue la misma logica: captura impulsos de sesion sin dejar correr perdidas.

## Configuración
- Símbolo   : `XAUUSD`
- Estrategia: `pullback` en `4h`
- ADX mín   : 25
- RR target : 2.5
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 1.030  ✗  (mín 1.2)
  WR     : 42.9%
  Trades : 35       ✓  (mín 30)
  DD     : 0.5%  ✓  (máx 10%)
  PnL    : $+9  (+0.1%)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
