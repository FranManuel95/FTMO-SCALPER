# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Trading Research Lab — backtesting and validating trading strategies for FTMO prop firm challenges. The goal is to find strategies with a real statistical edge that pass FTMO rules: max 5% daily loss, max 10% total drawdown, 10% profit target on Phase 1.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/unit/test_metrics.py -v

# ── RESEARCH LOOP (flujo principal para nueva estrategia) ──
# 1. Crear spec YAML en config/strategies/
# 2. Correr el pipeline automatizado:
python -m src.orchestration.run_research_loop --spec config/strategies/eurusd_pullback_1h.yaml
# El pipeline corre IS → OOS → Walk-Forward automáticamente y genera reporte en reports/

# Lint
ruff check src/

# Single strategy backtest (con trailing stop)
python -m src.orchestration.run_backtest --symbol XAUUSD --strategy pullback --timeframe 1h \
  --start 2023-01-01 --end 2025-01-01 --risk 0.004 --adx-min 25 --rr-target 2.5 \
  --exit-mode trail --trail-atr-mult 0.5

# Walk-forward + Monte Carlo validation (con trailing stop)
python -m src.orchestration.run_validation --symbol XAUUSD --strategy pullback --timeframe 1h \
  --start 2022-01-01 --end 2026-04-01 --risk 0.004 --adx-min 25 --rr-target 2.5 \
  --exit-mode trail --trail-atr-mult 0.5

# Walk-forward CON comisiones (--commission en USD/lot round-trip)
# Forex: 7.0 $/lot | XAUUSD: 35.0 $/lot (spread ~$0.35 × 100 oz)
python -m src.orchestration.run_validation --symbol XAUUSD --strategy pullback --timeframe 1h \
  --start 2022-01-01 --end 2026-04-01 --risk 0.004 --adx-min 25 --rr-target 2.5 \
  --exit-mode trail --trail-atr-mult 0.3 --commission 35.0

# Combined backtest (Breakout 15m + Pullback 1h, shared risk guards)
python -m src.orchestration.run_combined --symbol XAUUSD --start 2023-01-01 --end 2025-01-01 \
  --risk 0.005 --adx-min 25 --rr-target 2.5 --research

# Combined walk-forward validation
python -m src.orchestration.run_validation --symbol XAUUSD --strategy combined \
  --start 2022-01-01 --end 2025-01-01 --risk 0.005 --adx-min 25 --rr-target 2.5
```

All orchestration scripts use `--research` to disable MaxLossGuard (so the full period is simulated rather than stopping early when the guard triggers).

## Architecture

```
Orchestration (run_backtest, run_validation, run_combined)
      ↓
Signals (breakout/london_breakout, pullback/trend_pullback)
      ↓
Features (technical/indicators, trend/htf_filter, session/asian_range)
      ↓
Data loaders (mt5_csv → primary, yahoo → fallback)
      ↓
Risk (position_sizing, daily_loss_guard, max_loss_guard)
      ↓
Metrics (performance.summary, ftmo_checks.run_all_checks)
      ↓
Validation (walk_forward_efficiency, monte_carlo_pnl in run_validation.py)
```

**Key invariants:**
- Signals are stateless: they receive a DataFrame and return `list[Signal]`. No side effects.
- Exit simulation is bar-by-bar on the price data (first SL or TP hit wins). No partial fills.
- `size_by_fixed_risk` always uses `risk_amount / stop_distance`, so PnL per trade is always exactly `±risk_pct × balance × rr_target` regardless of asset price.
- All DataFrames use a UTC-aware `DatetimeIndex` named `datetime`.

## Data Setup

MT5 CSVs go in `backtest/data/` (primary) or `data/raw/` (fallback). Naming convention: `{SYMBOL}_{TF}.csv` where TF is `H1`, `M15`, `1H`, `15M`, etc. The loader `find_csv()` tries multiple suffixes automatically.

For combined strategies (15m + 1h), both CSVs must be present. Exits are always simulated on 15m data for higher resolution.

**Available CSV data (as of research):** XAUUSD, EURUSD, USDJPY, EURJPY, GBPJPY, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF, EURGBP — todos en 1H (+ 15M/4H/1D para la mayoría). Cobertura: 2022–2026-04. Los CSVs en `backtest/data/` están en UTC+2 (hora broker MT5).

## Indicator Library

`src/features/technical/indicators.py` and `src/features/trend/htf_filter.py` are dual-compatible: they prefer `talib` (C library, faster) and fall back to `ta` (pure Python). Both must produce identical column names. When adding new indicators, always maintain this pattern:

```python
try:
    import talib as _talib
    _USE_TALIB = True
except ImportError:
    _USE_TALIB = False
    from ta.trend import ...
```

HTF filters work by resampling the base DataFrame (e.g., 1h → 4h), computing EMAs on the resampled data, then joining back with `.ffill()`. This avoids loading a second CSV. See `add_htf_trend()`, `add_htf_adx()`, `add_daily_trend()`.

**Warmup requirements:** EMA200 daily needs ~200 bars ≈ 10 months. With data from Jan 2022, daily EMA200 is reliable from ~Oct 2022. Weekly EMA50 needs ~50 weeks ≈ 1 year — insufficient with Jan 2022 start.

## Strategies

### ✅ Trend Pullback — VALIDADA (`src/signals/pullback/trend_pullback.py`)

**XAUUSD 1H — ESTRATEGIA PRINCIPAL**
- **Best parameters:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.004`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **5.546**, P(profit) 100%, P(DD>10%) **0.0%**, PnL median $1213/6m en $10k
- **FTMO viability:** Safe at 0.4% risk. ~4–5 trades/month. Trail=0.3×ATR ($3.60 margen vs $0.40 spread) — suficiente separación para live trading.
- **Trail sweep result:** 0.2 da PF 10.856 OOS pero margen=$2.40 es demasiado ajustado vs spread en días de noticias. 0.3 es el sweet spot: edge máximo con seguridad de ejecución.

**USDJPY 1H — ESTRATEGIA SECUNDARIA (CONDITIONAL)**
- **Best parameters:** `adx_min=20`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.2`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **2.515**, P(ruin) 0.0%, PnL median $986/6m en $10k
- **FTMO viability:** Safe at 0.3% risk. Trail=0.2×ATR viable porque spread JPY (~0.5 pip) es irrelevante vs ATR 1H (~70 pips). Riesgo macro: BoJ hikes pueden revertir driver JPY.
- **Logic:** Same EMA20 pullback as XAUUSD but ADX threshold lowered to 20 (JPY crosses have lower ADX naturally). Both LONG and SHORT signals generated.

### ✅ NY Open Breakout — VALIDADA (`src/signals/breakout/ny_open_breakout.py`)

- **Asset/TF:** XAUUSD 15m
- **Logic:** Build range from NY open first hour (13:00-14:00 UTC = 15:00-16:00 broker). Breakout of range in H4 trend direction. ADX > 18.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.5`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **4.205**, P(ruin) **0.0%**, Max DD p95 **0.6%**
- **FTMO viability:** Safe at 0.25% risk. ~8-10 trades/month. PnL median ~€267/mes en €10k. Trail 0.5×ATR es clave — captura impulso inicial del CME open aunque el breakout falle.
- **Fixed TP baseline:** OOS 5/6, PF 1.345, DD p95 8.6% — el trail lo transforma completamente.
- **RR=4.0 tested but rejected:** OOS PF 1.368 (+marginal) but P(ruin) spikes to 9.4%, Max DD p95=11.5% (>FTMO limit). Keep RR=2.5.
- **NY ORB on other pairs:** No edge. EURUSD, USDJPY, GBPUSD, GBPJPY, EURJPY all inconsistent year-by-year. XAUUSD-only strategy.

### ✅ London Open ORB + Trail — VALIDADA (`src/signals/breakout/london_open_breakout.py`)

- **Asset/TF:** XAUUSD 15m
- **Logic:** Range 07:00-08:00 UTC (09:00-10:00 broker). Breakout entry 08:00-12:00 UTC. ADX > 18. Trail 0.5×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.5`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **2.907**, P(ruin) **0.0%**, Max DD p95 **0.5%**
- **FTMO viability:** ~€180/mes en €10k. PnL median $1.079 sobre 6 meses.
- **Clave:** Con fixed TP era FROZEN (IS PF=1.017). Trail 0.5×ATR la rescató completamente — los false breakouts de Londres se convierten en pequeñas ganancias en vez de -1R.

### ✅ USDJPY Asian Session ORB 1H + Trail — VALIDADA (`src/signals/breakout/asian_session_orb.py`)

- **Asset/TF:** USDJPY 1h
- **Logic:** Construir rango sesión asiática (23:00–07:00 UTC). Breakout entry 07:00–12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.2×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.2`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **24.893**, P(ruin) **0.0%**, Max DD p95 **0.5%**, WFE **2.335**
- **Trail sweep result:** 0.2 es el sweet spot — margen 4.8 pips vs spread 0.5 pip (ratio 9.6x). Pasar de trail=0.5 a trail=0.2 multiplica PF OOS x8 con mejor DD. El spread USDJPY es irrelevante frente al ATR 1H (~24 pips).
- **FTMO viability:** ~€1,207/6m en €10k. WFE > 1 indica robustez genuina — OOS supera IS.

### ✅ NZDUSD Pullback 1H + Trail — CONDITIONAL PASS (`src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** NZDUSD 1h
- **Logic:** EMA20 pullback, ADX > 22, H4 trend. Trail 0.4×ATR.
- **Best parameters:** `adx_min=22`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **2.398**, P(ruin) **0.0%**, Max DD p95 **1.5%**
- **Sweep result:** ADX=22 aumenta frecuencia a 31 trades/ventana (vs 20 con ADX=25). Trail=0.4 mantiene 6/6 donde trail=0.3 pierde W3. PnL median $789/6m supera incluso ADX=20 trail=0.5 ($782) con mejor PF.
- **Caveats:** Baja frecuencia (~21-46 trades/ventana). Riesgo macro RBNZ. Viable a 0.3% riesgo.

### ✅ AUDUSD Pullback 1H Long-Only + Trail — VALIDADA (`src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** AUDUSD 1h
- **Logic:** EMA20 pullback **LONG-ONLY**, ADX > 25, H4 trend alcista. Trail 0.3×ATR.
- **Best parameters:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.3`, `long_only=True`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **5.756**, P(ruin) **0.0%**, Max DD p95 **0.2%**, WFE **1.935**
- **Rescue story:** Versión bidireccional era FAIL (4/6). El 60% de señales SHORT arrastraban el resultado — AUD rebota sistemáticamente en regímenes mixtos. LONG-only captura únicamente los rallies commodity/risk-on. Trail=0.3 (vs 0.5) lleva de 4/6 a 6/6. ~7-8 trades/6m.
- **Caveats:** Baja frecuencia. Riesgo macro: ciclo RBA dovish vs Fed hawkish puede revertir el edge.

### ✅ FVG XAUUSD 1H (`src/signals/fvg/fair_value_gap.py`)

- **Asset/TF:** XAUUSD 1h
- **Logic:** Imbalance de 3 velas (Fair Value Gap). Entry cuando precio retrocede a zona FVG. ADX > 20, H4 trend.
- **Best parameters:** `adx_min=20`, `rr_target=2.5`, `risk_pct=0.002`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **1.571**, P(ruin DD>10%) **0.0%**, Max DD p95 **3.2%**, WFE **1.305**
- **Sweep result:** Base (risk=0.4%, trail=0.5) daba DD p95=10.1% y P(ruin)=5.2% — inviable. Bajar risk a 0.2% + trail=0.3 lleva DD a 3.2% y P(ruin) a 0.0%. Margen ejecución 0.3×ATR=$3.60-5.40 vs spread $0.30-0.50 (ratio 7-18x).
- **Rol:** Diversificador de alta frecuencia (~140 señales/6m). Edge delgado pero consistente. No reemplaza al pullback — complementa capturando imbalances institucionales cuando no hay setup EMA.

### ❌ AUDUSD Pullback 1H + Trail

- **Result:** FAIL — 4/6 OOS (2 ventanas perdedoras). WFE 0.433 < 0.5. Trail mejoró PF de 0.88 a 1.51 IS pero sin driver macro unidireccional (RBA vs Fed se cancelan). Descartado.

### ✅ GBPUSD Pullback 1H + Trail — VALIDADA (`src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** GBPUSD 1h
- **Logic:** EMA20 pullback en estructura alcista, ADX>25, filtro H4 trend. Trail 0.5×ATR.
- **Best parameters:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.004`, `exit_mode=trail`, `trail_atr_mult=0.5`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **2.817**, P(ruin) **0.0%**, Max DD p95 **1.9%**
- **FTMO viability:** ~€180/mes en €10k. Driver macro: BoE vs Fed.

### ✅ EURUSD London Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/london_open_breakout.py`)

- **Asset/TF:** EURUSD 15m
- **Logic:** Rango London Open 07:00-08:00 UTC. Breakout entry 08:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.5×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.5`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **3.978**, P(ruin) **0.0%**, Max DD p95 **0.6%**, WFE **1.287**
- **Trail sweep:** 0.3 da PF 9.372 pero margen 1.4 pips ≈ spread en noticias — inviable. 0.5 sweet spot con 2.4 pips de margen (ratio 2.4-4.8× vs spread EURUSD 0.5-1.0 pip).
- **FTMO viability:** ~$1,442/6m en $10k. ~14-16 trades/mes — mayor frecuencia que pullbacks. EURUSD es el par más líquido — ejecución limpia. Diversifica genuinamente del portfolio XAUUSD.

### ✅ EURJPY Asian Session ORB 1H + Trail — VALIDADA (`src/signals/breakout/asian_session_orb.py`)

- **Asset/TF:** EURJPY 1h
- **Logic:** Rango asiático 23:00-07:00 UTC. Breakout entry 07:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.3×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **9.356**, P(ruin) **0.0%**, Max DD p95 **0.6%**, WFE **1.581**
- **Trail sweep:** 0.2 (PF 20.878, margen 5 pips, 3-10× spread) > 0.3 sweet spot (PF 9.356, 7.5 pips, 5-15×) > 0.5 (PF 3.765). Trail=0.2 comparable a USDJPY Asian ORB (PF 20.878 vs 24.893). Sweet spot operacional: trail=0.3.
- **FTMO viability:** ~$1,604/6m en $10k. ~58 trades/6m OOS. Misma mecánica que USDJPY Asian ORB.

### ✅ USDCAD NY Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/ny_open_breakout.py`)

- **Asset/TF:** USDCAD 15m
- **Logic:** Rango NY Open 13:00-14:00 UTC. Breakout entry 14:00-18:00 UTC en dirección H4 trend. ADX > 18. Trail 0.4×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **4.471**, P(ruin) **0.0%**, Max DD p95 **0.6%**, WFE **0.823**
- **Key insight:** USDCAD pullback falla (IS PF 1.14 incluso con trail) porque USD y CAD se cancelan como tendencia sostenida. Pero NY ORB captura volatilidad event-driven (datos petróleo EIA 15:30 UTC, datos CAD 13:30 UTC). ORB no necesita driver macro unidireccional.
- **Trail=0.4 sweet spot:** margen 3.2-4.8 pips vs spread 1.5-2.0 pip (1.6-3.2×). Trail=0.3 demasiado ajustado. Trail=0.5 también viable.

### ✅ GBPJPY London Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/london_open_breakout.py`)

- **Asset/TF:** GBPJPY 15m
- **Logic:** Rango London Open 07:00-08:00 UTC. Breakout entry 08:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.4×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **5.282**, P(ruin) **0.0%**, Max DD p95 **0.4%**, WFE **1.073**
- **BoJ risk NEUTRALIZADO:** Duración media posición = 2 velas 15M (30 min). BoJ actúa 02:00-07:00 UTC; el rango 07:00-08:00 ya incorpora el shock. No hay overnight. Regla operacional: skip en días reunión BoJ (~8/año).
- **Trail sweep:** 0.3 (PF 9.242, margen 4.1 pips, ratio 2.1×, borderline) > 0.4 sweet spot (PF 5.282, 5.5 pips, 2.8×) > 0.5 (PF 3.522, 6.9 pips, 3.4×).
- Bidirectional pullback (4/6, BoJ risk) y LONG-only pullback (5/6 WFE 0.199, W5 PF 0.331) ambos rechazados.

### ✅ EURGBP Pullback 1H + Trail — CONDITIONAL PASS (`src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** EURGBP 1h
- **Logic:** EMA20 pullback, ADX > 25, H4 trend. Trail 0.3×ATR.
- **Best parameters:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **5/6 OOS profitable**, avg OOS PF **4.398**, P(ruin) **0.0%**, Max DD p95 **1.1%**, WFE **3.171**
- **W3 failure:** H1 2024 — convergencia BoE/ECB elimina driver direccional. Mismo riesgo macro que la mean reversion EURGBP que falló. Trail=0.3 (margen 12-18 pips vs spread 1-2 pips, ratio 6-18×).
- **Status:** Documentado, no en live runner — añadir si se quiere aumentar diversificación con monitoreo BoE/ECB.

### ✅ USDCHF Pullback 1H + Trail — CONDITIONAL PASS (`src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** USDCHF 1h
- **Logic:** EMA20 pullback, ADX > 25, H4 trend. Trail 0.3×ATR. Driver: Fed vs SNB.
- **Best parameters:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.004`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **5/6 OOS profitable**, avg OOS PF **2.669**, P(ruin) **0.0%**, Max DD p95 **2.0%**, WFE **1.143**
- **W6 failure:** H2 2025 — USD weakness post-tarifas, CHF safe-haven appreciation. Trail=0.3 margen 4.2 pips vs spread 1.5-2 pips (ratio 2.1-2.8×, mínimo aceptable).
- **SNB risk:** Intervenciones sorpresa (2015 unpeg, 2022-2023) pueden crear gaps de 300+ pips — trailing stop 1H no protege. Requiere monitoreo humano.
- **Status:** Documentado, no en live — sustituido por USDCHF London ORB 15M que resuelve el riesgo SNB.

### ✅ AUDUSD Asian Session ORB 1H + Trail — VALIDADA (`src/signals/breakout/asian_session_orb.py`)

- **Asset/TF:** AUDUSD 1h
- **Logic:** Construir rango sesión asiática (23:00-07:00 UTC). Breakout entry 07:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.3×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.3`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **7.073**, P(ruin) **0.0%**, Max DD p95 **0.2%**, WFE **1.260**
- **Trail sweep:** 0.5 (PF 2.706) → 0.4 (PF 4.090) → 0.3 (PF 7.073, sweet spot) → 0.2 (PF 16.303). AUDUSD spread 0.4-0.8 pip vs ATR 50pip — incluso trail=0.2 da ratio 25×, sin restricción. Sweet spot trail=0.3 para robustez conservadora (WFE 1.260).
- **Tesis confirmada:** AUD es la divisa asiática primaria (Sydney, RBA, datos China). La misma mecánica que USDJPY Asian ORB (PF 24.893) y EURJPY Asian ORB (PF 9.356) — cuarto miembro de la familia Asian ORB. AUD define el rango asiático, London lo rompe estructuralmente.
- **Trade count:** ~40-59 trades/6m (~7-10/mes). Statistically meaningful.
- **FTMO viability:** ~$982/6m en $10k. DD p95 0.2% — el más bajo de todas las estrategias live.

### ✅ EURGBP London Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/london_open_breakout.py`)

- **Asset/TF:** EURGBP 15m
- **Logic:** Rango London Open 07:00-08:00 UTC. Breakout entry 08:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.4×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **4.967**, P(ruin) **0.0%**, Max DD p95 **0.5%**, WFE **1.122**
- **Trail sweep:** trail=0.5 (PF 3.293) → trail=0.4 sweet spot (PF 4.967) → trail=0.3 (PF 8.171, margin 1.8-3 pip vs spread 1-2 pip, demasiado ajustado). IS Gate 1: PF 3.289.
- **Hallazgo clave:** W3 (H1 2024, convergencia BoE/ECB) OOS PF = **4.651** con trail=0.4 — el mismo régimen que destruye el pullback EURGBP (5/6) es neutral o positivo para el ORB. La convergencia crea consolidación pre-London → breakout más limpio.
- **Execution margin:** ATR 15M 6-10 pip × 0.4 = 2.4-4 pip vs spread 1-2 pip (ratio 1.2-4×, aceptable).
- **FTMO viability:** ~$1,576/6m en $10k. ~14-17 trades/mes.

### ✅ USDCHF London Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/london_open_breakout.py`)

- **Asset/TF:** USDCHF 15m
- **Logic:** Rango London Open 07:00-08:00 UTC. Breakout entry 08:00-12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.4×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows):** **6/6 OOS profitable**, avg OOS PF **6.848**, P(ruin) **0.0%**, Max DD p95 **0.4%**, WFE **1.309**
- **Trail sweep:** 0.5 (PF 4.577) → 0.4 sweet spot (PF 6.848) → 0.3 (PF 10.848, extraordinario pero margin 1.2-2.4× spread, borderline en días CPI/SNB). IS Gate 1: PF 4.598.
- **SNB gap risk NEUTRALIZADO:** Ventana rango 07:00-08:00 UTC incorpora horario habitual SNB (09:30 Zurich = 07:30 UTC). Posiciones cierran antes 12:00 UTC, sin overnight. Mismo mecanismo que BoJ risk en GBPJPY London ORB.
- **Execution margin:** ATR 15M 8-12 pip × 0.4 = 3.2-4.8 pip vs spread 1.5-2 pip (ratio 1.6-3.2×).
- **FTMO viability:** ~$1,890/6m en $10k. ~85-90 trades/6m.
- **USDCHF NY ORB 15M** (PF 4.094, 6/6) documentado pero excluido — correlaciona con USDCAD NY ORB (ambos capturan volatilidad CME open / US data). London ORB añade exposición diferente.

- **USDCHF NY ORB 15M** (PF 4.094, 6/6) documentado pero excluido — correlaciona con USDCAD NY ORB (ambos capturan volatilidad CME open / US data). London ORB añade exposición diferente.

### ✅ GBPJPY Asian Session ORB 1H + Trail — VALIDADA (`src/signals/breakout/asian_session_orb.py`)

- **Asset/TF:** GBPJPY 1h
- **Logic:** Construir rango sesión asiática (23:00–07:00 UTC). Breakout entry 07:00–12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.2×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.2`
- **Walk-forward (2022–2026, 6 windows, CON comisión $7/lot):** **6/6 OOS profitable**, avg OOS PF **26.792**, P(ruin) **0.0%**, Max DD p95 **0.6%**, WFE **2.921**
- **Trail sweep (con comisión):** 0.2 (PF 26.792, sweet spot) → 0.3 (PF 8.434) → 0.4 (PF 4.595). Mismo patrón que USDJPY Asian ORB.
- **Execution margin:** ATR 1H GBPJPY ~90 pips × 0.2 = 18 pips vs spread 2-3 pips (ratio 6-9×). Seguro.
- **Correlación con GBPJPY London ORB:** Ambas pueden activarse el mismo día pero en ventanas distintas (Asian ORB entry 07:00, London ORB entry 08:00). Riesgo combinado diario: ~0.6% máximo. DailyLossGuard cubre.
- **W1 OOS PF 81.530 (H1 2023):** Probablemente régimen específico (BoJ YCC + GBP recovery). Sin W1, las otras 5 ventanas dan PF medio 15.8. Edge sigue siendo extraordinario fuera del outlier.
- **FTMO viability:** 6º miembro confirmado de la familia Asian ORB. JPY define el rango 23:00-07:00 UTC; GBP rompe con el impulso institucional de London open.

### ✅ NZDUSD Asian Session ORB 1H + Trail — VALIDADA (`src/signals/breakout/asian_session_orb.py`)

- **Asset/TF:** NZDUSD 1h
- **Logic:** Construir rango sesión asiática (23:00–07:00 UTC). Breakout entry 07:00–12:00 UTC en dirección H4 trend. ADX > 18. Trail 0.2×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.003`, `exit_mode=trail`, `trail_atr_mult=0.2`
- **Walk-forward (2022–2026, 6 windows, CON comisión $7/lot):** **6/6 OOS profitable**, avg OOS PF **8.731**, P(ruin) **0.0%**, Max DD p95 **0.4%**, WFE **1.713**
- **Trail sweep (con comisión):** 0.2 (PF 8.731, sweet spot) → 0.3 (PF 4.718) → 0.4 (PF 2.761). NZD spread 0.8-1.5 pip vs ATR 1H 40 pips → margen 8 pips (ratio 5-10×).
- **5º miembro familia Asian ORB:** NZD es divisa asiática primaria (RBNZ, datos lácteos, correlación China). Mismo mecanismo que AUDUSD Asian ORB (PF 4.346) — Sydney/Wellington define el rango, London lo rompe.
- **W2 y W5 WFE < 0.5:** OOS siempre positivo (PF 2.806 y 4.528) pero IS superó mucho al OOS. No compromete la robustez global (6/6 OOS profitable).
- **FTMO viability:** ~$900/6m en $10k. DD p95 0.4% — el más bajo de la nueva selección.

### ✅ GBPUSD NY Open ORB 15M + Trail — VALIDADA (`src/signals/breakout/ny_open_breakout.py`)

- **Asset/TF:** GBPUSD 15m
- **Logic:** Rango NY Open 13:00-14:00 UTC. Breakout entry 14:00-18:00 UTC en dirección H4 trend. ADX > 18. Trail 0.4×ATR.
- **Best parameters:** `adx_min=18`, `rr_target=2.5`, `risk_pct=0.0025`, `exit_mode=trail`, `trail_atr_mult=0.4`
- **Walk-forward (2022–2026, 6 windows, CON comisión $7/lot):** **6/6 OOS profitable**, avg OOS PF **3.696**, P(ruin) **0.0%**, Max DD p95 **0.6%**, WFE **0.994**
- **Consistencia excepcional:** Rango OOS PF 2.474-4.104 — la variabilidad más baja de todos los ORBs. Ningún periodo flojea.
- **Ejecución:** ATR 15M GBPUSD ~10-15 pips × 0.4 = 4-6 pips vs spread 0.8-1.5 pip (ratio 3-7×). Seguro.
- **Driver:** GBPUSD muy reactivo a datos US (NFP, CPI, PCE) y datos UK (BoE, retail sales). CME open crea impulso estructural.
- **GBPUSD London ORB 15m** (trail=0.4, PF 3.006, 6/6, CON comisión): Documentado pero excluido — evitar dos ORBs en el mismo par sin reducir risk. NY ORB es más consistente (WFE 0.994 vs 1.248).
- **FTMO viability:** ~$1,200/6m en $10k. ~90-100 trades/6m. Alta frecuencia + alta consistencia = fiable para FTMO targets.

### ❌ London Breakout (`src/signals/breakout/london_breakout.py`)

- **Asset/TF:** XAUUSD 15m
- **Logic:** Asian range identified 00:00–07:00 UTC; breakout confirmed by close outside range + buffer; ADX > 22; range size between 0.5x–4x ATR
- **Result:** FAIL Gate 1 IS 2022-2025 — PF 0.970, DD 12.8%. Catastrófico en mercados laterales (2022-2023). Misma dependencia de régimen que el pullback — combinarlos amplifica pérdidas.

### ❌ BB Mean Reversion (`src/signals/mean_reversion/bb_reversion.py`)

- **Asset/TF:** EURUSD 1h y XAUUSD 1h (ambos testados)
- **Logic:** LONG cuando close < BB lower + RSI oversold + ADX < adx_max; TP = BB midline
- **EURUSD resultado:** Régimen-dependiente. 2022 PF 0.67, 2023 PF 1.01, 2024 PF 1.80, 2025 PF 0.19. Sin consistencia entre años — no viable.
- **XAUUSD resultado:** WR ~27% en todos los años, PF ~0.92-1.07. Sin edge claro.
- **Nota data:** CSVs backtest/data usan UTC+2 (hora broker). El loader ahora prioriza backtest/data sobre data/raw.

### Combined (`src/orchestration/run_combined.py`)

Loads both 15m and 1h, merges signals sorted by timestamp, simulates all exits on 15m data, shared DailyLossGuard. Enabled `daily_trend_enabled=True` by default (EMA50 vs EMA200 on daily). **Research conclusion: combined is worse than pullback alone** — both strategies fail in the same market regime (XAUUSD ranging), so combining doubles losses in bad periods (W1 OOS: -$1,925, DD 21% vs -$820, DD 8.2% for pullback alone).

## Validation Framework

Walk-forward in `run_validation.py` uses anchored windows: `IS=12m, OOS=6m, step=6m` by default.

**Walk-Forward Efficiency (WFE):** `(OOS_PF - 1) / (IS_PF - 1)` — measures what fraction of IS edge survives OOS. Returns `None` when IS PF < 1.2 (denominator too small, ratio unstable). Target ≥ 0.5.

**Verdict logic (primary → secondary):**
1. OOS pass rate ≥ 50% AND avg OOS PF ≥ 1.3 → "ROBUSTA" or "MARGINAL"
2. Pass rate ≥ 50% but WFE clearly negative → "DEPENDIENTE DE RÉGIMEN"
3. Otherwise → "INESTABLE"

**Monte Carlo** in `monte_carlo_pnl()` resamples OOS trade PnLs with replacement (5000 sims). DD values are absolute (positive = worse). `p50/p90/p95` of max DD are worst-case percentiles (increasing left to right).

## Commission Modeling

`run_backtest` y `run_validation` tienen el parámetro `--commission` (USD/lot round-trip). No afecta al live runner (que opera con spread y comisiones reales del broker).

**Valores estándar** para broker IC Markets / FTMO partner:
- Forex majors: `--commission 7.0` ($3.5 entrada + $3.5 salida)
- XAUUSD: `--commission 35.0` (spread típico $0.35 × 100 oz/lot; sin comisión separada)

**Resultados con comisión (walk-forward 2022-2026, 6 ventanas):**

| Estrategia | PF sin comisión | PF con comisión | Δ | Estado |
|------------|----------------|----------------|---|--------|
| XAUUSD Pullback 1h | 5.546 | **4.027** | −27% | 6/6 ✓ |
| XAUUSD London ORB 15m | 2.907 | **1.534** | −47% | 5/6 ⚠️ |
| XAUUSD NY ORB 15m | 9.216 | **2.730** | −70% | 6/6 ✓ |
| EURUSD London ORB 15m | 3.978 | **2.334** | −41% | 6/6 ✓ |
| GBPJPY London ORB 15m | 5.282 | **5.267** | −0.3% | 6/6 ✓ |
| USDCHF London ORB 15m | 6.848 | **3.524** | −49% | 6/6 ✓ |
| EURGBP London ORB 15m | 4.967 | **1.982** | −60% | 6/6 ✓ |
| USDCAD NY ORB 15m | 4.472 | **3.129** | −30% | 6/6 ✓ |
| USDJPY Asian ORB 1h | 24.893 | **24.780** | −0.5% | 6/6 ✓ |
| EURJPY Asian ORB 1h | 9.356 | **9.333** | −0.2% | 6/6 ✓ |
| AUDUSD Asian ORB 1h | 7.073 | **4.346** | −39% | 6/6 ✓ |
| GBPJPY Asian ORB 1h | NEW | **26.792** | — | 6/6 ✓ |
| NZDUSD Asian ORB 1h | NEW | **8.731** | — | 6/6 ✓ |
| GBPUSD NY ORB 15m | NEW | **3.696** | — | 6/6 ✓ |

**Insight clave:** Los pares JPY (USDJPY, EURJPY) y GBPJPY apenas se ven afectados porque el spread en JPY es irrelevante vs el ATR. XAUUSD sufre más porque el spread ($35/lot) es alto relativo al tamaño de posición en estrategias con trailing corto (15M ORB). Las 3 Asian ORB 1h son las más robustas a costes de transacción.

**XAUUSD London ORB alerta:** Con comisión baja a 5/6 y PF 1.534 — edge fino pero real. Monitorear en live con atención especial. Si el broker cobra menos spread (ej. $0.20 × 100 = $20/lot), el PF con comisión sería ~2.0-2.5.

## Known Research Findings

- **Regime dependency is fundamental for XAUUSD trend strategies.** XAUUSD H1 2023 (ranging) consistently gives WR ~10%, PF ~0.27. XAUUSD H2 2023–2024 (bull run) gives WR 42–50%, PF 1.8–2.5. No filter tested successfully separated these regimes because gold was already in a daily golden cross (EMA50 > EMA200) even during the ranging period — it's a secular bull market.
- **Daily ADX filter made performance worse** — too correlated with the hourly ADX already in use.
- **Weekly EMA50 regime had no effect** — insufficient warmup with Jan 2022 data start.
- **Daily EMA50 vs EMA200 filter had no effect** — gold's secular bull means EMA50 > EMA200 during ranging periods too.
- **Optimal risk for pullback XAUUSD:** 0.4% per trade. Raising to 0.5% would push worst-case OOS DD to ~10.3% (breaches FTMO limit).
- **EURUSD pullback FAIL:** 0 winning trades (WR 0%) — EURUSD is not a trending instrument in the same way as XAUUSD.
- **EURUSD mean reversion:** Régimen-dependiente. Con datos correctos (UTC+2): 2022 PF 0.67, 2023 PF 1.01, 2024 PF 1.80, 2025 PF 0.19. Sin consistencia entre años. El buen resultado de 2023 previo (PF 4.6) era un artefacto del CSV UTC mal interpretado como UTC+2.
- **XAUUSD mean reversion:** WR ~27% en todos los años. No complementario al pullback — fallan juntos.
- **Multi-par scan completo (pullback):** USDJPY CONDITIONAL (validado a 0.3% riesgo). EURJPY con trail=0.3 da OOS 5/6 PF 4.747 pero IS PF=1.073 falla Gate 1 y trade counts muy bajos (9-26/ventana) — documentado, no en live. GBPJPY con trail FAIL 4/6 (W5 más reciente PF 0.682, BoJ gap risk descarta para live). AUDUSD FAIL (avg PF ~0.88). USDCAD FAIL Gate 1 con trail (IS PF=1.14). EURGBP CONDITIONAL PASS 5/6 PF 4.398 — documentado. USDCHF CONDITIONAL PASS 5/6 PF 2.669 — documentado. El edge EMA pullback requiere driver macro unidireccional fuerte.
- **EURUSD London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 3.978, DD p95 0.6%, WFE 1.287, trail=0.5 (margen 2.4 pips vs spread 0.5-1.0 pip). Supera XAUUSD London ORB (PF 2.907). ~14-16 trades/mes, alta frecuencia. Trail=0.3 da PF 9.4 teórico pero margen 1.4 pips demasiado ajustado en días de noticias. AÑADIDA AL LIVE RUNNER. Trail/ADX sweep confirmó: ADX=18 + RR=2.5 + trail=0.5 es el óptimo. ADX=22 arregla W2 WFE pero reduce PnL 33%. RR=3.0 estrictamente peor.
- **EURUSD NY Open ORB 15M CONDITIONAL:** 6/6 OOS, PF 2.745, DD p95 0.6%, pero W1 (PF 1.139) y W6 (PF 1.589) thin. Más débil que London ORB. Documentado, no en live runner.
- **EURUSD pullback FAIL:** 0 winning trades (WR 0%) — EURUSD no es instrumento trending.
- **EURJPY Asian Session ORB 1H ROBUSTA:** 6/6 OOS, PF 9.356 (trail=0.3), WFE 1.581, DD p95 0.6%, ~58 trades/6m. Trail sweep: 0.2 (PF 20.878) > 0.3 (PF 9.356, sweet spot) > 0.5 (PF 3.765). Misma mecánica que USDJPY Asian ORB (PF 24.893) aplicada a EUR/JPY. JPY establece rango asiático, EUR rompe en London open. AÑADIDA AL LIVE RUNNER (trail=0.3).
- **EURJPY London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 4.031, DD p95 0.6%, ~85 trades/6m. Documentado, no en live — correlaciona con EURUSD London ORB (mismo horario, EUR como driver).
- **USDCAD NY Open ORB 15M ROBUSTA:** 6/6 OOS, PF 4.471 (trail=0.4), WFE 0.823, DD p95 0.6%, ~90 trades/6m. El pullback USDCAD falla porque USD/CAD se cancelan como tendencia, pero el ORB captura volatilidad event-driven (datos petróleo, datos CAD). AÑADIDA AL LIVE RUNNER (trail=0.4). Trail=0.3 too tight (margen 2.4-3.6 pip vs spread 1.5-2.0 pip). Trail=0.5 también viable.
- **USDCAD London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 4.083 (trail=0.4), DD p95 0.5%. Documentado, no en live — evitar dos ORBs simultáneas en mismo par sin reducir riesgo.
- **GBPJPY London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 5.282 (trail=0.4), WFE 1.073, DD p95 0.4%, ~87 trades/6m. Clave: BoJ gap risk NEUTRALIZADO — trades cierran en 30-45 min (mediana 2 velas 15M). BoJ actúa 02:00-07:00 UTC, entradas a las 08:00 UTC. El rango 07:00-08:00 UTC ya incorpora cualquier shock BoJ. AÑADIDA AL LIVE RUNNER (trail=0.4). Regla operacional: no operar en días reunión BoJ (~8/año). LONG-only pullback (5/6 pero WFE 0.199, W5 PF 0.331) y bidirectional pullback (4/6) ambos rechazados.
- **XAUUSD 15M pullback:** FAIL — misma dependencia de régimen que 1H (2023 PF ~0.90 arrastra IS a ~1.06). Más señales no compensan la misma exposición al régimen.
- **EURGBP mean reversion:** FAIL — régimen-dependiente: 2021-2022 PF>1.5, 2023 PF=0.829, 2024 PF=1.53, 2025 PF=1.03. Sin consistencia inter-año.
- **XAUUSD mean reversion 1H:** FAIL — no es complementaria al pullback. Falla en 2022 (gold cayendo por hikes Fed) al igual que el pullback. LONG-only tampoco ayuda: 2022 PF=0.696.
- **London Breakout 15M (Asian range):** FAIL Gate 1 con IS 2022-2025 (PF 0.97, DD 12.8%). Diferente a London Open ORB — rango asiático, no rango London.
- **London Open ORB 15M con trail 0.5×ATR:** PASS 6/6. Con fixed TP era FROZEN (PF=1.017). Trail lo rescata → PF 2.907, DD p95 0.5%. El trail convierte false breakouts en pequeñas ganancias.
- **GBPUSD Pullback 1H con trail 0.5×ATR:** PASS 6/6, PF 2.817, DD p95 1.9%. Driver BoE vs Fed. Misma lógica EMA20 que XAUUSD.
- **XAUUSD Pullback 4H:** FAIL Gate 1 (IS PF=1.030). Pocas señales en 4H durante 2022-2023 (ranging) arrastra el IS.
- **NY Open ORB 15M con trail 0.5×ATR:** WF 6/6 OOS, avg PF 4.205, Max DD p95 0.6%, P(ruin) 0.0%. El trail captura el impulso inicial del CME open — incluso breakouts fallidos dan pequeñas ganancias. Fixed TP baseline (1.345) era delgado; trail lo transforma en edge sólido. RR=4.0 testado y rechazado (P(ruin)=9.4%).
- **Trail ATR sweep completo (todas las estrategias):** PF aumenta monotónicamente al apretar el trail. Sweet spots por estrategia: XAUUSD Pullback 1H → trail=0.3 (PF OOS 5.546, 6/6, margen $3.60 > spread $0.40); USDJPY Pullback 1H → trail=0.2 (PF OOS 2.515, 6/6, spread JPY irrelevante); NY ORB 15M → trail=0.5 (trail=0.3 teórico da PF 9.216 pero margen $1.20 ≈ spread en noticias). La lógica: `trail_sl = bar["high"] - atr * mult`. Implementado en `run_backtest.py` exit_mode="trail".
- **Partial TP (50% a 1.5R) resultó PEOR:** Recorta ganadores antes de tiempo. El precio que llega a 1.5R tiende a continuar a 2.5R. Fixed o trail son mejores que partial.
- **Partial TP (50% a 1.5R) resultó PEOR:** Recorta ganadores antes de tiempo. El precio que llega a 1.5R tiende a continuar a 2.5R. Fixed o trail son mejores que partial.
- **Data timezone:** CSVs en backtest/data/ usan UTC+2 (hora broker MT5). El sistema usa tz_offset_hours=2 para ser consistente. Nunca mezclar con CSVs UTC-naive de data/raw/.
- **run_research_loop bug fixed:** Mean reversion params (rsi_oversold, rsi_overbought, bb_std) were not passed from YAML → run_backtest → BBReversionConfig. Fixed.
- **Asian ORB family estructural (6 miembros confirmados):** USDJPY (PF 24.780), GBPJPY (PF 26.792), EURJPY (PF 9.333), NZDUSD (PF 8.731), AUDUSD (PF 4.346) forman familia con comisión incluida. GBPJPY es el nuevo líder junto a USDJPY. NZD confirma el 5º miembro (Sydney + RBNZ + datos China = divisa asiática primaria). PFs calculados con comisión $7/lot. La tesis: la divisa asiática primaria (JPY, AUD) define el rango 23:00-07:00 UTC. London rompe el rango estructuralmente con flujos institucionales. No funciona en pares EUR/USD (EUR es divisa London, no asiática). AUDUSD es el cuarto miembro confirmado (Sydney, RBA, China data definen el rango). ATR 1H 50 pip vs spread 0.4-0.8 pip da ratio de ejecución 12-37×.
- **AUDUSD Asian ORB 1H ROBUSTA:** 6/6 OOS, PF 7.073 (trail=0.3), WFE 1.260, DD p95 0.2%, P(ruin) 0.0%. Trail sweep: 0.2→16.303 (ratio ejecución 25×, incluso más seguro que USDJPY 9.6×), sweet spot trail=0.3 por conservadurismo. AUDUSD London ORB (PF 2.161, W4 OOS=1.020) y NY ORB (PF 2.334) ambos documentados pero excluidos. AÑADIDA AL LIVE RUNNER (trail=0.3, risk=0.3%).
- **EURGBP London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 4.967 (trail=0.4), WFE 1.122, DD p95 0.5%, P(ruin) 0.0%. IS Gate 1: PF 3.289. Trail sweep: 0.5→3.293, 0.4→4.967 (sweet spot), 0.3→8.171 (margin 1.8-3 pip ≈ spread en noticias, excluido). HALLAZGO CLAVE: W3 (H1 2024, convergencia BoE/ECB que mata el pullback) OOS PF=4.651 — la convergencia que destruye el pullback crea consolidación pre-London que favorece el ORB. EURGBP NY ORB (PF 2.594) documentado pero excluido (no poner 2 ORBs en mismo par). AÑADIDA AL LIVE RUNNER (trail=0.4, risk=0.25%).
- **USDCHF London Open ORB 15M ROBUSTA:** 6/6 OOS, PF 6.848 (trail=0.4), WFE 1.309, DD p95 0.4%, P(ruin) 0.0%. IS Gate 1: PF 4.598. Trail sweep: 0.5→4.577, 0.4→6.848 (sweet spot), 0.3→10.848 (margin 2.4-3.6 pip, ratio 1.2-2.4× borderline en días CPI). SNB RISK NEUTRALIZADO: rango 07:00-08:00 UTC incorpora horario habitual SNB (07:30 UTC), cierre antes 12:00 UTC. Mismo mecanismo que BoJ neutralization en GBPJPY. USDCHF NY ORB (PF 4.094) documentado pero excluido (correlación con USDCAD NY ORB). AÑADIDA AL LIVE RUNNER (trail=0.4, risk=0.25%).

## Risk Guards

`DailyLossGuard`: tracks cumulative PnL per calendar day; blocks new signals once daily loss ≥ 5% of initial balance.

`MaxLossGuard`: tracks total drawdown; blocks all signals once total loss ≥ 10% of initial balance.

In `--research` mode both guards are disabled so the full period's performance is visible.

## Reports

All backtest outputs go to `reports/strategy_reports/`. JSON contains full metrics + `trade_pnls` list. CSV contains the trade log. Walk-forward validation saves `{SYMBOL}_{STRATEGY}_{TF}_validation.json` with per-window results, WFE, Monte Carlo, and verdict.

## Research Loop Automatizado

El flujo estándar para cualquier estrategia nueva es:

1. **Crear spec** en `config/strategies/{nombre}.yaml` — define símbolo, parámetros, períodos y gates de aceptación
2. **Correr el pipeline**: `python -m src.orchestration.run_research_loop --spec config/strategies/{nombre}.yaml`
3. El pipeline aplica automáticamente la lógica de las skills:
   - **Gate 1 IS**: `review_backtest_results` — red flags, PF, DD, trades mínimos
   - **Gate 2 OOS**: `compare_experiments` — degradación IS→OOS, estabilidad
   - **Gate 3 WF**: walk-forward + Monte Carlo — robustez temporal, P(ruin)
4. Si pasa los 3 gates → reporte markdown en `reports/strategy_reports/` + spec YAML actualizado con veredicto

**Para proponer una nueva estrategia sin saber trading**: describe la idea en lenguaje informal → yo genero la spec YAML y la corro. Tú solo apruebas o ajusta.

## Skills Available

Skills in `skills/` are prompt templates for specific research tasks:
- `review_backtest_results.md` — structured critique of a backtest (red flags: PF>3 with few trades, WR>70% with RR<1, DD>8%, IS→OOS degradation >30%)
- `generate_strategy_spec.md` — converts a trading idea into a testable spec
- `compare_experiments.md` — side-by-side comparison of parameter sweeps
- `build_feature_pipeline.md` — scaffolds a new feature/indicator

When reviewing backtest results, always check: PF stability IS→OOS, per-window OOS consistency, Monte Carlo P(DD>10%), and whether trade count is statistically sufficient (≥30 trades per period).

## Live Trading System

### Arquitectura completa

```
Windows PC (MT5 machine)
─────────────────────────────────────────────────────────────
  start_bot.bat (doble click en escritorio)
    └─ python -m src.live.run_live --live --confirm "I UNDERSTAND"
         │
         ├─ PortfolioRunner.tick() cada 30s
         │    ├─ MT5 bars → signal generators → orders
         │    ├─ TrailManager.update_all() (trailing stops)
         │    ├─ _maybe_check_anomalies() cada 30 min
         │    └─ _maybe_send_weekly_report() domingos 08:00 UTC
         │
         ├─ Background thread: _listen_telegram_commands() cada 5s
         │    ├─ /stop  → para el bot limpiamente
         │    └─ /status → responde con posiciones y balance
         │
         ├─ escribe → data/events.db  (SQLite, indexado)
         └─ escribe → data/events.jsonl (backup append-only)
                           │
  ftmo-dashboard (servicio Windows, auto-start)
    └─ streamlit run dashboard/app.py
         └─ lee data/events.db en modo read-only
              └─ http://localhost:8501 (PC)
              └─ http://100.80.131.15:8501 (Tailscale, móvil/remoto)
─────────────────────────────────────────────────────────────
```

### Archivos clave del sistema live

| Archivo | Responsabilidad |
|---------|----------------|
| `src/live/run_live.py` | Entry point CLI (`--live`, `--check`, `--dry-run`, `--no-events`) |
| `src/live/portfolio_runner.py` | Loop principal, trail, guards, anomaly check, weekly report |
| `src/live/trail_manager.py` | Trailing stop bar-by-bar. **BUG CRÍTICO CORREGIDO:** usar solo barras DESPUÉS de `entry_time` (`bars_after = df[df.index > pd.Timestamp(pos.entry_time)]`). Si se incluye la barra de señal el trailing arranca con el low intrabar y puede disparar inmediatamente. |
| `src/live/order_manager.py` | MT5 orders, `LivePosition`, slippage medido en pips |
| `src/live/event_logger.py` | Dual-write JSONL+SQLite, thread-safe, 8 tipos de evento |
| `src/live/notifier.py` | Telegram send+receive. `get_commands()` sondea getUpdates. |
| `src/live/live_data_loader.py` | Descarga barras cerradas de MT5 en UTC |

### Bug del trail manager (corregido, no reintroducir)

**Síntoma:** 45% de trades cerraban en < 5 minutos como "quick-stop".

**Causa:** `TrailManager` usaba `df.iloc[-1]` para inicializar `highest/lowest_since_entry`. La barra de señal es la misma barra en la que se abre la posición — su `low` intrabar ya está por debajo del precio de entrada para una SELL, por lo que `trail_sl = bar_low + ATR×mult` queda por encima del entry y cualquier tick al alza dispara el SL.

**Fix:** Filtrar solo las barras cerradas DESPUÉS de `entry_time`:
```python
bars_after = df[df.index > pd.Timestamp(pos.entry_time)]
if bars_after.empty:
    continue  # No hay barras nuevas desde la entrada — esperar
```

### Recuperación de posiciones al reinicio

Al arrancar, `_recover_open_positions()` escanea MT5 buscando posiciones abiertas con el magic number. Para cada una reconstruye `LivePosition` con el `highest/lowest_since_entry` correcto consultando las barras históricas desde `entry_time`. Así el trailing retoma sin interrupciones aunque el bot se reinicie.

### EventLogger — tipos de evento

Todos los eventos tienen: `event_id`, `ts` (ISO UTC), `ts_unix`, `event_type`, `strategy_id`, `symbol`, `ticket`, `payload` (JSON).

| event_type | Cuándo | Campos clave en payload |
|-----------|--------|------------------------|
| `strategy_tick` | Cada iteración por estrategia | `n_bars`, `fetch_ms`, `generator_ms`, `n_signals`, `n_executed`, `error` |
| `signal` | Cada señal generada | `side`, `entry_price`, `stop_loss`, `take_profit`, `was_executed`, `filter_reason` |
| `guard_check` | Cuando un guard bloquea | `guard_name`, `triggered`, `reason` |
| `order` | Orden enviada a MT5 | `fill_price`, `slippage_pips`, `volume`, `intended_volume` |
| `trail_update` | Cada evaluación de trail | `applied`, `new_sl`, `skip_reason` |
| `position_close` | Cierre detectado | `pnl`, `net`, `duration_seconds`, `close_reason`, `mfe`, `mae` |
| `system_event` | bot_start/stop, mt5_disconnect, position_recovered, weekly_report_sent | variado |
| `market_snapshot` | Cada minuto | `balance`, `equity`, `n_open_positions`, `daily_pnl` |

`close_reason` inferido comparando `exit_price` con `original_sl` / `stop_loss` (trail) / `take_profit` con tolerancia 5%.

### Dashboard — páginas

```
dashboard/
  app.py                    # Overview: balance, equity, FTMO progress, posiciones abiertas
  lib/
    data.py                 # SQLite loaders con @st.cache_data(ttl=30)
    metrics.py              # Cálculos puros (sin streamlit): trade_summary, detect_anomalies, etc.
    formatting.py           # fmt_eur, fmt_pct, fmt_pips, fmt_duration, severity_color
  pages/
    2_Strategies.py         # PF/WR/expectancy por estrategia, drift detector
    3_Execution.py          # Slippage, quick-stop rate, latencias
    4_Trades.py             # Histórico filtrable, curva equity, CSV download
    5_Inspector.py          # Timeline completa de un ticket (SL/TP/trail + JSON)
    6_Anomalies.py          # Detección automática con severidad y recomendaciones
```

`detect_anomalies(closes_df, orders_df)` detecta: quick-stop rate > 50%, racha 4+ pérdidas, slippage Z-score > 2.5, lot size 3σ. Esta misma función la llama `PortfolioRunner._check_and_alert_anomalies()` cada 30 minutos para alertas Telegram.

### Telegram — comandos y alertas automáticas

| Trigger | Mensaje |
|---------|---------|
| `/stop` | Para el bot limpiamente (via `threading.Event`) |
| `/status` | Responde con posiciones abiertas y balance |
| Anomalía high/medium | Alerta inmediata con título y detalle. Dedup por `category:title` para no repetir. |
| Domingo ≥ 08:00 UTC | Resumen semanal: trades, WR, P&L, desglose por estrategia, balance actual |

El polling de comandos es un daemon thread que usa `_stop_event.wait(timeout=5)` — se detiene automáticamente al parar el bot.

### Infraestructura Windows

**Servicio ftmo-dashboard** (auto-start con Windows):
```
NSSM → C:\ftmo-scalper\.venv\Scripts\python.exe -m streamlit run dashboard/app.py ...
Logs: C:\ftmo-scalper\logs\dashboard-service.log
```

**Bot** (arranque manual, requiere sesión de usuario para MT5):
```
Acceso directo en escritorio → scripts/services/start_bot.bat
```
El bot NO puede ser servicio SYSTEM porque MT5 corre en la sesión del usuario y los procesos de distintas cuentas no comparten la comunicación IPC de MT5.

**Scripts de gestión:**
- `scripts/services/install_services.ps1` — instala/reinstala ambos servicios (requiere Admin)
- `scripts/services/uninstall_services.ps1` — elimina los servicios
- `scripts/services/start_bot.bat` — lanzador del bot (acceso directo en escritorio)
- `scripts/services/bot_control.ps1 {start|stop|status|logs}` — control desde PowerShell

**Acceso remoto:** Tailscale VPN. PC: `100.80.131.15`, móvil: `100.114.199.116`. Dashboard accesible en `http://100.80.131.15:8501` desde cualquier red.

### Variables de entorno (.env)

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=...
FTMO_EVENTS_DB=data/events.db       # opcional, default
FTMO_EVENTS_JSONL=data/events.jsonl # opcional, default
```

### Próximas mejoras pendientes

- **Filtro de noticias**: bloquear señales 30 min antes/después de eventos macro (calendario económico API). Especialmente relevante para EURGBP (0W/4L semana 1).
- **VPS dashboard (Nivel 2)**: mover Streamlit a un VPS Linux barato (€5/mes), sincronizar `events.db` cada minuto vía rsync sobre Tailscale. Dashboard siempre accesible aunque el PC del bot se reinicie.
- **EURGBP monitoring**: la estrategia es CONDITIONAL PASS (5/6 OOS). Monitorear si W3 (convergencia BoE/ECB) se repite en 2026.
- **Notificación de inicio de semana**: lunes 07:00 UTC — recordatorio de qué estrategias están activas y el estado de los guards.

