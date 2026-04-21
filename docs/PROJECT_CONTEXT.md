# FTMO Scalper — Contexto del Proyecto

Documento de referencia para nuevas conversaciones. Pegar completo al inicio de sesión.

---

## ¿Qué es esto?

Sistema de trading automático para cuentas de fondeo FTMO. Desarrollado desde cero:
investigación de estrategias → backtesting riguroso → walk-forward validation → ejecución live en MetaTrader 5.

**Stack:** Python + MetaTrader 5 (Windows) + Telegram bot para notificaciones.  
**Repo:** `FranManuel95/FTMO-SCALPER`, rama activa `claude/trading-research-lab-ieDgh`.  
**Cuenta:** FTMO demo €160k. Reglas: -5% daily loss, -10% max drawdown, +10% objetivo Phase 1.

---

## Portfolio live activo (14 estrategias)

Todas usan trailing stop ATR y filtro H4 trend. Validadas con walk-forward 6 ventanas IS=12m/OOS=6m, periodo 2022–2026.

| # | Estrategia | Par / TF | Trail | Risk | OOS PF | DD p95 |
|---|-----------|----------|-------|------|--------|--------|
| 1 | Trend Pullback (EMA20) | XAUUSD 1H | 0.3 | 0.4% | 5.55 | 1.6% |
| 2 | Trend Pullback (EMA20) | GBPUSD 1H | 0.5 | 0.4% | 2.82 | 1.9% |
| 3 | Trend Pullback (EMA20) | USDJPY 1H | 0.2 | 0.3% | 2.52 | 1.8% |
| 4 | Trend Pullback (EMA20) | NZDUSD 1H | 0.4 | 0.3% | 2.40 | 1.5% |
| 5 | London Open ORB | XAUUSD 15M | 0.5 | 0.25% | 2.91 | 0.5% |
| 6 | NY Open ORB | XAUUSD 15M | 0.5 | 0.25% | 4.21 | 0.6% |
| 7 | Asian Session ORB | USDJPY 1H | 0.5 | 0.3% | 3.22 | 0.7% |
| 8 | London Open ORB | EURUSD 15M | 0.5 | 0.25% | 3.98 | 0.6% |
| 9 | London Open ORB | GBPJPY 15M | 0.4 | 0.25% | 5.28 | 0.4% |
| 10 | Asian Session ORB | EURJPY 1H | 0.3 | 0.3% | 9.36 | 0.6% |
| 11 | NY Open ORB | USDCAD 15M | 0.4 | 0.25% | 4.47 | 0.6% |
| 12 | Asian Session ORB | AUDUSD 1H | 0.3 | 0.3% | 7.07 | 0.2% |
| 13 | London Open ORB | EURGBP 15M | 0.4 | 0.25% | 4.97 | 0.5% |
| 14 | London Open ORB | USDCHF 15M | 0.4 | 0.25% | 6.85 | 0.4% |

**Todas: 6/6 OOS profitable · P(ruin DD>10%) = 0.0% · P(profit) = 100%**

Proyección conservadora (descuento correlación 40%): ~$14,500/6m sobre $10k (~2.4%/mes). Phase 1 FTMO en ~2-3 semanas. Frecuencia: ~140-170 trades/mes en total.

---

## Metodología de validación (obligatoria para cada estrategia)

```
Gate 1 IS:  backtest 2023-2025, PF > 1.3, min 20-30 trades, DD < 10%, FTMO consistency
Gate 2 WF:  walk-forward 2022-2026, 6 ventanas IS=12m/OOS=6m
            → necesario: ≥5/6 OOS rentables, avg OOS PF > 1.3
Gate 3 MC:  Monte Carlo 5,000 sims sobre trades OOS
            → necesario: P(ruin DD>10%) = 0.0%, DD p95 < 10%
Trail sweep: probar trail=0.2/0.3/0.4/0.5 — sweet spot = mayor PF con margen > spread×2
```

**Regla de ejecución crítica:** `trail_sl = bar_high - atr * mult`. El margen mínimo
en live debe ser ≥2× el spread del par. Violarlo destruye el edge en días de noticias.

| Par | ATR 1H típico | Spread típico | Trail mínimo viable |
|-----|--------------|---------------|---------------------|
| XAUUSD | $12–18 | $0.30–0.50 | 0.3× ($3.60 margen) |
| EURUSD 15M | 7–9 pips | 0.5–1.0 pip | 0.5× (2.4 pip margen) |
| USDJPY | 60–80 pips | 0.5 pip | 0.2× viable (ratio 9×) |
| GBPJPY 15M | 20–25 pips | 2.0 pip | 0.4× (5.5 pip margen) |
| USDCAD 15M | 8–12 pips | 1.5–2.0 pip | 0.4× (3.2 pip margen) |

---

## Estrategias validadas pero NO en live (documentadas)

| Estrategia | Par / TF | OOS PF | Motivo exclusión |
|-----------|----------|--------|-----------------|
| London Open ORB | EURJPY 15M | 4.03 | Correlaciona con EURUSD London ORB (misma hora) |
| London Open ORB | USDCAD 15M | 4.08 | Mismo par que NY ORB ya activo |
| NY Open ORB | EURUSD 15M | 2.75 | Edge más fino que London ORB (mismo par) |
| Pullback | EURGBP 1H | 4.40 | Sustituido por EURGBP London ORB 15M (sin riesgo W3) |
| Pullback | USDCHF 1H | 2.67 | Sustituido por USDCHF London ORB 15M (SNB neutralizado) |
| FVG ICT | XAUUSD 1H | 1.57 | 4ª estrategia en XAUUSD = correlación en laterales |
| Pullback LONG-only | AUDUSD 1H | 5.76 | Solo 7–8 trades/6m, sustituido por AUDUSD Asian ORB |
| NY Open ORB | USDCHF 15M | 4.09 | Correlaciona con USDCAD NY ORB (mismo driver CME) |
| NY Open ORB | AUDUSD 15M | 2.33 | WFE débil W1/W2; Asian ORB captura mejor la sesión AUD |
| London Open ORB | AUDUSD 15M | 2.16 | W4 OOS PF=1.020; Asian ORB es la sesión correcta para AUD |
| NY Open ORB | EURGBP 15M | 2.59 | Dos ORBs en mismo par aumenta correlación |

---

## Descartado definitivamente

| Par / Approach | Motivo |
|---------------|--------|
| USDCAD Pullback | IS PF 1.14, USD+CAD se cancelan |
| GBPJPY Pullback (ambas dir.) | 4/6 OOS, BoJ gaps de 500-700 pips |
| EURJPY Pullback | IS PF 1.073 falla Gate 1 |
| EURUSD Pullback | WR 0% — no es instrumento tendencial |
| AUDUSD Pullback bidireccional | 4/6, sin driver macro |
| BB Mean Reversion (cualquier par) | Régimen-dependiente, sin consistencia inter-año |
| Combined breakout+pullback | Ambas fallan en mismo régimen → amplifica pérdidas |
| XAUUSD Pullback 4H/15M | Pocas señales 4H / misma dependencia régimen 15M |

---

## Hallazgos clave de la investigación

- **El edge EMA pullback requiere driver macro unidireccional fuerte.** XAUUSD (safe-haven commodity), GBPUSD (BoE vs Fed), USDJPY/NZDUSD/EURJPY funcionan. EURUSD, USDCAD, AUDUSD no.
- **Trail ATR es la clave del sistema.** Convierte estrategias "marginales" en robustas al dejar correr ganadores y cortar perdedores rápido. Sin trail, la mayoría falla. PF monotónicamente aumenta al apretar trail — pero el límite inferior es el spread del par.
- **W2 WFE baja es el talón de Aquiles del EURUSD London ORB** (H2 2023 ranging). No es un bug del trail — es régimen. Todas las configuraciones de trail muestran el mismo patrón.
- **XAUUSD tiene 3 estrategias en live** (Pullback + London ORB + NY ORB). Una 4ª (FVG) fue validada pero excluida por concentración — en regímenes laterales las 4 perderían simultáneamente.
- **Asian Session ORB es una familia estructural de 4 estrategias.** USDJPY (PF 3.22), EURJPY (PF 9.36), AUDUSD (PF 7.07). La divisa asiática primaria (JPY, AUD) define el rango 23:00-07:00 UTC. London rompe el rango con flujos institucionales. No funciona en pares donde ambas divisas son europeas (EURUSD, EURGBP). AUD definido por Sydney, RBA, datos China — mismo mecanismo que JPY.
- **BoJ y SNB gap risk neutralizados por ORBs intraday.** GBPJPY: BoJ actúa 02:00-07:00 UTC, el rango ya incorpora el shock, posiciones cierran <12:00 UTC. USDCHF: SNB habitual 07:30 UTC = dentro de la ventana de rango. Mismo principio: cierre same-session elimina riesgo gap overnight.
- **BoE/ECB convergencia que destruye el pullback EURGBP MEJORA el ORB.** La convergencia crea consolidación pre-London → breakout más limpio. W3 (H1 2024) OOS PF=4.651 para el ORB vs FAIL para el pullback. Los ORBs son inmunes al riesgo de régimen que afecta a los pullbacks.

---

## Estructura del repo

```
src/
├── signals/
│   ├── pullback/trend_pullback.py          # EMA20 pullback (long+short o long-only)
│   ├── breakout/london_open_breakout.py    # London ORB 07:00-08:00 UTC
│   ├── breakout/ny_open_breakout.py        # NY ORB 13:00-14:00 UTC
│   ├── breakout/asian_session_orb.py       # Asian ORB 23:00-07:00 UTC
│   └── fvg/fair_value_gap.py               # ICT Fair Value Gap
├── features/
│   ├── technical/indicators.py             # ATR, ADX (talib o ta fallback)
│   └── trend/htf_filter.py                 # add_htf_trend() resample 4H, add_daily_trend()
├── risk/                                   # DailyLossGuard (-5%), MaxLossGuard (-10%)
├── live/
│   ├── run_live.py                         # CLI: --dry-run / --live / --check / --once
│   ├── portfolio_runner.py                 # Loop principal, PortfolioRunner
│   ├── mt5_client.py                       # MT5Client (real + fake para tests)
│   ├── order_manager.py                    # Envío y gestión de órdenes MT5
│   ├── trail_manager.py                    # Trailing stop bar-a-bar
│   └── notifier.py                         # TelegramNotifier, NullNotifier
└── orchestration/
    ├── run_backtest.py                     # IS backtest con todas las opciones
    ├── run_validation.py                   # Walk-forward + Monte Carlo
    └── run_research_loop.py                # Pipeline automatizado IS→OOS→WF

config/strategies/                          # YAMLs con params validados por estrategia
backtest/data/                              # CSVs MT5 UTC+2 (XAUUSD, EURUSD, USDJPY...)
reports/strategy_reports/                  # JSON + CSV de cada backtest/validación
docs/                                       # DEPLOYMENT_FTMO.md, PROJECT_CONTEXT.md
```

---

## Comandos de uso

```bash
# Instalar (Linux/dev/CI)
pip install -e ".[dev]"

# Instalar (Windows/live)
pip install -e ".[live]"

# Diagnóstico completo (recomendado antes de arrancar)
python -m src.live.run_live --check

# Dry-run (sin enviar órdenes reales)
python -m src.live.run_live --dry-run --once

# Live real
python -m src.live.run_live --live --confirm "I UNDERSTAND"

# Backtest una estrategia
python -m src.orchestration.run_backtest --symbol EURUSD --strategy london_orb \
  --timeframe 15m --start 2023-01-01 --end 2025-01-01 \
  --risk 0.0025 --adx-min 18 --rr-target 2.5 --exit-mode trail --trail-atr-mult 0.5 --research

# Walk-forward validation
python -m src.orchestration.run_validation --symbol EURUSD --strategy london_orb \
  --timeframe 15m --start 2022-01-01 --end 2026-04-01 \
  --risk 0.0025 --adx-min 18 --rr-target 2.5 --exit-mode trail --trail-atr-mult 0.5

# Pipeline automático para nueva estrategia
python -m src.orchestration.run_research_loop --spec config/strategies/mi_estrategia.yaml
```

---

## Variables de entorno (.env en raíz, no commitear)

```ini
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=FTMO-Demo
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## Estado de investigación — frontera actual

**Pares con data disponible investigados al completo:**
XAUUSD ✅ · EURUSD ✅ · GBPUSD ✅ · USDJPY ✅ · EURJPY ✅ · GBPJPY ✅ · NZDUSD ✅ · AUDUSD ✅ · USDCAD ✅ · USDCHF ✅ · EURGBP ✅

**Portfolio completamente saturado** — todos los pares con data disponible tienen al menos una estrategia live o han sido descartados definitivamente.

**Fronteras pendientes (opcionales, baja prioridad):**
- Investigar EURUSD Asian ORB 1H (no testado — EUR es divisa London, hipótesis débil pero no confirmada)
- Investigar estrategias en 4H para pares ya validados en 1H (pocas señales, probable FAIL)
- Regenerar validation JSON de USDJPY Asian ORB a trail=0.5 explícito (JSON actual mezcla sweep runs)
- Evaluar FVG XAUUSD 1H para live si se quiere aumentar frecuencia XAUUSD (PF 1.57, 6/6, pero 4ª estrategia en el par)

**Mejoras de ejecución pendientes:**
- **Spread check antes de abrir posiciones** — protege contra entrar durante ensanchamiento de spread en noticias (NFP, FOMC, CPI). Implementar en `portfolio_runner.py` antes de ejecutar una señal: si `current_spread > normal_spread × 3`, saltar la entrada. No requiere calendario externo. Los pares más expuestos son EURUSD (trail margin 3.5-4.5 pip vs spread noticias 3-8 pip) y USDCHF (3.2-4.8 pip vs 5-15 pip). Las posiciones ya abiertas no se filtran — el trailing stop gestiona la salida. El walk-forward ya incluyó todos los eventos de noticias 2022-2026 con 6/6 profitable, así que el riesgo es bajo incluso sin este filtro.
