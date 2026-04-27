# FTMO Scalper — Live Portfolio Reference

**Última actualización:** Abril 2026  
**Objetivo FTMO:** Phase 1 — 10% profit target, max 5% daily loss, max 10% total drawdown

---

## Portfolio Activo (20 estrategias)

### Parámetros de cada estrategia en el live runner

| # | strategy_id | Symbol | TF | Risk % | Trail | PF OOS | Win Rate | Ventanas | DD p95 |
|---|-------------|--------|----|--------|-------|--------|----------|----------|--------|
| 1 | xauusd_pullback_1h | XAUUSD | 1h | 0.4% | 0.3 | 5.546 | 42–50% | 6/6 | 0.5% |
| 2 | gbpusd_pullback_1h | GBPUSD | 1h | 0.4% | 0.5 | 2.325* | 52–68% | 6/6 | 2.2% |
| 3 | usdjpy_pullback_1h | USDJPY | 1h | 0.3% | 0.2 | 2.515 | 45–55% | 6/6 | 1.5% |
| 4 | nzdusd_pullback_1h | NZDUSD | 1h | 0.3% | 0.4 | 2.398 | 40–50% | 6/6 | 1.5% |
| 5 | xauusd_ny_orb_15m | XAUUSD | 15m | 0.25% | 0.5 | 2.730* | 50–60% | 6/6 | 0.6% |
| 6 | xauusd_london_orb_15m | XAUUSD | 15m | 0.25% | 0.3 | 2.905* | 50–59% | 6/6 | 0.5% |
| 7 | eurusd_london_orb_15m | EURUSD | 15m | 0.25% | 0.5 | 2.334* | 50–60% | 6/6 | 0.6% |
| 8 | gbpjpy_london_orb_15m | GBPJPY | 15m | 0.25% | 0.4 | 5.267* | 55–65% | 6/6 | 0.4% |
| 9 | eurgbp_london_orb_15m | EURGBP | 15m | 0.25% | 0.3 | 2.742* | 50–53% | 6/6 | 0.7% |
| 10 | usdchf_london_orb_15m | USDCHF | 15m | 0.25% | 0.4 | 3.524* | 55–65% | 6/6 | 0.4% |
| 11 | usdcad_ny_orb_15m | USDCAD | 15m | 0.25% | 0.4 | 3.129* | 50–60% | 6/6 | 0.6% |
| 12 | gbpusd_ny_orb_15m | GBPUSD | 15m | 0.25% | 0.4 | 3.696* | 57–60% | 6/6 | 0.6% |
| 13 | usdjpy_asian_orb_1h | USDJPY | 1h | 0.3% | 0.2 | 24.780* | 65–80% | 6/6 | 0.5% |
| 14 | eurjpy_asian_orb_1h | EURJPY | 1h | 0.3% | 0.3 | 9.333* | 65–75% | 6/6 | 0.6% |
| 15 | audusd_asian_orb_1h | AUDUSD | 1h | 0.3% | 0.3 | 4.346* | 60–70% | 6/6 | 0.2% |
| 16 | gbpjpy_asian_orb_1h | GBPJPY | 1h | 0.3% | 0.2 | 26.792* | 70–85% | 6/6 | 0.6% |
| 17 | nzdusd_asian_orb_1h | NZDUSD | 1h | 0.3% | 0.2 | 8.731* | 65–80% | 6/6 | 0.4% |
| 18 | usdcad_asian_orb_1h | USDCAD | 1h | 0.3% | 0.2 | 8.505* | 65–75% | 6/6 | 0.2% |
| 19 | gbpusd_asian_orb_1h | GBPUSD | 1h | 0.3% | 0.2 | 6.916* | 65–72% | 6/6 | 0.8% |

> `*` = PF ajustado con comisión ($7/lot forex, $35/lot XAUUSD)  
> PF sin `*` = sin comisión (estrategia validada antes de la modelización de costes)

---

## Análisis de Riesgo del Portfolio

### Exposición máxima teórica (peor caso: todas las estrategias entran y pierden)

| Grupo | Estrategias | Riesgo total |
|-------|-------------|-------------|
| Pullbacks 1h | 4 | 0.4+0.4+0.3+0.3 = **1.4%** |
| London ORBs 15m | 5 | 5 × 0.25 = **1.25%** |
| NY ORBs 15m | 3 | 3 × 0.25 = **0.75%** |
| Asian ORBs 1h | 7 | 7 × 0.3 = **2.1%** |
| **TOTAL TEÓRICO** | 19 | **5.5%** |

> El DailyLossGuard para en -5% antes de alcanzar el máximo teórico.

### Exposición diaria realista

No todas las estrategias generan señal cada día. Según datos históricos:
- **Pullbacks:** 1-2 por día (requieren setup EMA + ADX)
- **London ORBs:** 2-3 por día (09:00-12:00 UTC, broker time)
- **NY ORBs:** 1-2 por día (13:00-18:00 UTC)
- **Asian ORBs:** 2-4 por día (07:00-12:00 UTC)

**Riesgo diario típico:** ~2.0-3.5% (sumando las estrategias que actualmente generan señal)

### Concentración por símbolo

| Símbolo | Estrategias | Max riesgo diario por símbolo |
|---------|-------------|-------------------------------|
| XAUUSD | Pullback + NY ORB + London ORB (3) | 0.4+0.25+0.25 = **0.9%** |
| GBPUSD | Pullback + NY ORB + Asian ORB (3) | 0.4+0.25+0.3 = **0.95%** |
| GBPJPY | London ORB + Asian ORB (2) | 0.25+0.3 = **0.55%** |
| USDCAD | NY ORB + Asian ORB (2) | 0.25+0.3 = **0.55%** |
| NZDUSD | Pullback + Asian ORB (2) | 0.3+0.3 = **0.6%** |
| USDJPY | Pullback + Asian ORB (2) | 0.3+0.3 = **0.6%** |
| EURUSD | London ORB (1) | **0.25%** |
| EURJPY | Asian ORB (1) | **0.3%** |
| AUDUSD | Asian ORB (1) | **0.3%** |
| EURGBP | London ORB (1) | **0.25%** |
| USDCHF | London ORB (1) | **0.25%** |

---

## Ventanas Horarias de Operación

```
UTC TIME   00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
           ──────────────────────────────────────────────────────────────────────────────────────────────
ASIAN ORB  │────────── RANGE BUILD (23:00-07:00) ──────────────────────────│ ENTRY (07:00-12:00) │
LONDON ORB                                                   │ RANGE │ ENTRY (08:00-12:00) │
NY ORB                                                                       │ RNG │ ENTRY (14:00-18:00) │
PULLBACK   │────────────────────────── SESSION (09:00-23:00 broker) ──────────────────────────────────────│
```

**Broker time** = UTC+2. Conversión: broker_hour = utc_hour + 2.

### Reglas operacionales críticas

| Situación | Acción |
|-----------|--------|
| Reunión BoJ (~8×/año) | Skip GBPJPY London ORB + GBPJPY Asian ORB ese día |
| Decisión BoE/ECB (~20×/año) | Skip EURGBP London ORB ese día (spread se dispara) |
| SNB announcement (~4×/año, ~07:30 UTC) | Monitorear USDCHF Asian ORB (rango 07:00 ya incorpora el shock) |
| NFP/CPI/PCE (primer viernes del mes) | Monitorear todo el portfolio — DailyLossGuard protege |
| RBNZ announcement | Monitorear NZDUSD estrategias |

---

## Estrategias Validadas NO Activas en Live

Documentadas para referencia — excluidas por correlación o baja frecuencia:

| Estrategia | PF OOS | Razón de exclusión |
|-----------|--------|-------------------|
| EURUSD Asian ORB 1h | 4.525 (6/6) | Solapa con EURUSD London ORB (ambas 07:00-12:00 UTC) |
| USDCHF Asian ORB 1h | 7.225 (6/6) | Solapa con USDCHF London ORB (ambas 07:00-12:00 UTC) |
| AUDUSD London ORB 15m | 2.161 (5/6) | W4 OOS débil, complemento insuficiente |
| EURUSD NY ORB 15m | 2.745 (6/6) | Más débil que London ORB en EURUSD |
| USDCAD London ORB 15m | 4.083 (6/6) | 2 ORBs en el mismo par sin reducir riesgo |
| USDCHF NY ORB 15m | 4.094 (6/6) | Correlaciona con USDCAD NY ORB (ambos CME open) |
| EURJPY London ORB 15m | 4.031 (6/6) | Correlaciona con EURUSD London ORB (EUR driver) |
| GBPUSD London ORB 15m | 3.006 (6/6) | 3 ORBs en GBPUSD sería demasiado |
| FVG XAUUSD 1h | 1.571 (6/6) | Edge delgado, 4ª estrategia en XAUUSD |
| EURGBP Pullback 1h | 4.398 (5/6) | W3 falla (convergencia BoE/ECB). Conditional pass. |
| USDCHF Pullback 1h | 2.669 (5/6) | W6 falla (USD debilidad 2025). SNB gap risk. |

---

## Configuración MT5 Requerida

### Magic numbers (auto-asignados por strategy_id)

El `order_manager.py` no usa magic numbers configurables — cada orden MT5 la coloca `MetaTrader5.order_send()`. Verificar que las órdenes llevan comentario = strategy_id para reconciliación.

### Símbolos requeridos en el terminal MT5

```
XAUUSD  — broker: "XAUUSD" o "XAUUSDm"
GBPUSD  — broker: "GBPUSD"
USDJPY  — broker: "USDJPY"
NZDUSD  — broker: "NZDUSD"
EURUSD  — broker: "EURUSD"
GBPJPY  — broker: "GBPJPY"
EURGBP  — broker: "EURGBP"
USDCHF  — broker: "USDCHF"
USDCAD  — broker: "USDCAD"
EURJPY  — broker: "EURJPY"
AUDUSD  — broker: "AUDUSD"
```

> Verificar con `--check` que todos los símbolos resuelven: `python -m src.live.run_live --check`

### Barras requeridas por estrategia

| Timeframe | Barras (StrategyConfig.bars_to_fetch) | Uso |
|-----------|--------------------------------------|-----|
| 15m | ~500 barras (~5 días) | NY ORB, London ORB |
| 1h | ~300 barras (~12 días) | Pullback, Asian ORB |

Los builders usan `AsianSessionORBConfig`, `LondonOpenBreakoutConfig`, etc. con sus defaults. El `bars_to_fetch` se define en `StrategyConfig` — verificar que cubre suficiente historial para EMA200 diario y H4 trend.

---

## Checklist Pre-Deployment

### Antes de activar `--live` en producción

- [ ] Ejecutar `python -m src.live.run_live --check` — verificar 0 errores
- [ ] Verificar `.env` tiene: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- [ ] Confirmar balance FTMO inicial y limits con `--check` (el bot los loguea en startup)
- [ ] Ejecutar `--dry-run` durante al menos 1 sesión completa (London + NY) y verificar señales en Telegram
- [ ] Verificar dashboard `http://localhost:8501` accesible (o via Tailscale en móvil)
- [ ] Verificar `data/events.db` se crea y escribe correctamente
- [ ] Verificar que el servicio `ftmo-dashboard` arranca automáticamente con Windows

### Verificación periódica (semanal)

- [ ] Revisar dashboard página `6_Anomalies` — quick-stop rate, racha pérdidas, slippage
- [ ] Revisar `2_Strategies` — PF por estrategia en live vs backtest histórico (drift > 30% es señal)
- [ ] Revisar `3_Execution` — slippage promedio < 1 pip en forex, < $0.50 en XAUUSD
- [ ] FTMO account: verificar balance vs trailing max drawdown, días de trading

---

## Cómo Añadir una Nueva Estrategia Validada

1. **Crear build function** en `run_live.py` (copia la más similar):
   ```python
   def build_SYMBOL_strategy_TF():
       from src.signals.breakout.asian_session_orb import AsianSessionORBConfig, generate_asian_session_orb_signals
       cfg = AsianSessionORBConfig(adx_min=18, rr_target=2.5, htf_trend_enabled=True)
       def gen(df): return generate_asian_session_orb_signals(df, cfg)
       return gen
   ```

2. **Añadir StrategyConfig** en `build_default_portfolio()`:
   ```python
   StrategyConfig(
       strategy_id="symbol_strategy_tf",
       symbol="SYMBOL", timeframe="1h",
       risk_pct=0.003, trail_atr_mult=0.2,
       generator=build_SYMBOL_strategy_tf(),
   ),
   ```

3. **Verificar** con `--check` que el nuevo generator funciona con datos reales de MT5

4. **Dry-run** durante una sesión completa antes de activar en `--live`

---

## Expected Monthly P&L (commission-adjusted, $10k account)

Estimaciones basadas en Monte Carlo OOS (medianas):

| Estrategia | PnL median/6m | PnL median/mes |
|-----------|--------------|----------------|
| xauusd_pullback_1h | $1,213 | ~$200 |
| gbpusd_pullback_1h | $909 | ~$150 |
| usdjpy_pullback_1h | $986 | ~$165 |
| nzdusd_pullback_1h | $789 | ~$130 |
| xauusd_ny_orb_15m | ~$450 | ~$75 |
| xauusd_london_orb_15m | $909 | ~$150 |
| eurusd_london_orb_15m | $1,442 | ~$240 |
| gbpjpy_london_orb_15m | ~$800 | ~$133 |
| eurgbp_london_orb_15m | $1,003 | ~$167 |
| usdchf_london_orb_15m | $1,890 | ~$315 |
| usdcad_ny_orb_15m | ~$600 | ~$100 |
| gbpusd_ny_orb_15m | ~$1,200 | ~$200 |
| usdjpy_asian_orb_1h | $1,207 | ~$200 |
| eurjpy_asian_orb_1h | $1,604 | ~$267 |
| audusd_asian_orb_1h | $982 | ~$164 |
| gbpjpy_asian_orb_1h | ~$1,500 | ~$250 |
| nzdusd_asian_orb_1h | $900 | ~$150 |
| usdcad_asian_orb_1h | $1,121 | ~$187 |
| gbpusd_asian_orb_1h | $2,040 | ~$340 |
| **TOTAL PORTFOLIO** | **~$20,545** | **~$3,424/mes** |

> Advertencia: estas son medianas Monte Carlo OOS de estrategias probadas por separado. En portfolio real, las correlaciones y el DailyLossGuard reducirán tanto las ganancias como las pérdidas. Estimación realista portfolio: 50-70% del total independiente = ~$1,700-$2,400/mes en $10k.

---

## Umbrales FTMO Phase 1 (cuenta $10k)

| Métrica | Límite | Nuestra exposición estimada |
|---------|--------|-----------------------------|
| Max Daily Loss | -$500 (5%) | DailyLossGuard en -$500. Riesgo típico/día ~$200-350 |
| Max Total DD | -$1,000 (10%) | MaxLossGuard en -$1,000. DD p95 más alto: 2.2% (GBPUSD pullback) |
| Profit Target | +$1,000 (10%) | Median Monte Carlo portfolio: ~$3,424/mes → esperado en ~9-12 días |
| Min Trading Days | 4 days/month | Con 19 estrategias hay señales virtualmente todos los días |

