# Research Report: XAUUSD Breakout 15m
Generated: 2026-04-20 15:59

## Hipótesis
London Breakout sobre rango asiatico (00:00-07:00 UTC). Cuando el precio rompe el rango con confirmacion ADX>22 y tamano de rango 0.5x-4x ATR, se entra en la direccion del breakout. Complementaria al pullback 1H: genera mas operaciones en dias con momentum. Hipotesis: funciona bien en 2024-2026 (bull run oro).

## Configuración
- Símbolo   : `XAUUSD`
- Estrategia: `breakout` en `15m`
- ADX mín   : 22
- RR target : 2.0
- Risk/trade: 0.40%

## Gate 1 — In-Sample
Período: `2022-01-01` → `2025-01-01`
  PF     : 0.970  ✗  (mín 1.2)
  WR     : 32.7%
  Trades : 199       ✓  (mín 30)
  DD     : 12.8%  ✗  (máx 10%)
  PnL    : $-160  (-1.6%)
  ⚠ DD 12.8% > 8% — peligroso para FTMO (límite 10%)

**Status: FAIL ✗** — pipeline detenido

## Veredicto Final
**FAIL en Gate 1 (IS) — edge insuficiente o DD excesivo en muestra**
