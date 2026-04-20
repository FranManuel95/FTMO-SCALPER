# Research Report: EURUSD Pullback 1h
Generated: 2026-04-20 14:08

## Hipótesis
Si el pullback en tendencia funciona en XAUUSD, debería manifestarse también en EURUSD H1 — mismo setup de EMA20/50 + ADX. Validar si el edge es del tipo de estrategia o específico del activo (oro tiene sesgo alcista secular).

## Configuración
- Símbolo   : `EURUSD`
- Estrategia: `pullback` en `1h`
- ADX mín   : 25
- RR target : 2.5
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2024-01-01`
  PF     : 0.000  ✗  (mín 1.2)
  WR     : 0.0%
  Trades : 21       ✗  (mín 30)
  DD     : 8.4%  ✓  (máx 10%)
  PnL    : $-840  (-8.4%)
  ⚠ DD 8.4% > 8% — peligroso para FTMO (límite 10%)
  ⚠ Solo 21 trades — insuficiente para significancia estadística

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
