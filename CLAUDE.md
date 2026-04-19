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

# Lint
ruff check src/

# Single strategy backtest
python -m src.orchestration.run_backtest --symbol XAUUSD --strategy pullback --timeframe 1h \
  --start 2023-01-01 --end 2025-01-01 --risk 0.004 --adx-min 25 --rr-target 2.5

# Walk-forward + Monte Carlo validation
python -m src.orchestration.run_validation --symbol XAUUSD --strategy pullback --timeframe 1h \
  --start 2022-01-01 --end 2025-01-01 --risk 0.004 --adx-min 25 --rr-target 2.5

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

**Available CSV data (as of research):** `XAUUSD_1H.csv`, `XAUUSD_M15.csv`, `EURUSD_H1.csv` covering 2022–2025.

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

### Trend Pullback (best tested — `src/signals/pullback/trend_pullback.py`)

- **Asset/TF:** XAUUSD 1h
- **Logic:** Price above EMA50 + EMA20 > EMA50 (bullish structure); pullback below EMA20 then close back above it; RSI < 60; ADX > threshold
- **Key filters:** H4 trend (EMA50 > EMA200 on H4 resample), session 09:00–23:00 broker time
- **Best parameters found:** `adx_min=25`, `rr_target=2.5`, `risk_pct=0.004`
- **Walk-forward results (2022–2025, 4 windows):** 3/4 OOS profitable, avg OOS PF 1.724, Monte Carlo P(profit) 94.5%, P(DD>10%) 1.3%
- **FTMO viability:** Safe at 0.4% risk (worst-case OOS DD 8.2% < 10% limit). ~4 trades/month; expect 12–18 months to hit 10% target in favorable conditions.

### London Breakout (`src/signals/breakout/london_breakout.py`)

- **Asset/TF:** XAUUSD 15m
- **Logic:** Asian range identified 00:00–07:00 UTC; breakout confirmed by close outside range + buffer; ADX > 22; range size between 0.5x–4x ATR
- **Best OOS result:** PF 2.25 in 2024 bull run
- **Regime dependency:** Catastrophic in ranging markets (IS 2022–2023: PF 0.709). Same correlation as pullback — combining both amplifies losses in bad regimes without diversification benefit.

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

## Known Research Findings

- **Regime dependency is fundamental for XAUUSD trend strategies.** XAUUSD H1 2023 (ranging) consistently gives WR ~10%, PF ~0.27. XAUUSD H2 2023–2024 (bull run) gives WR 42–50%, PF 1.8–2.5. No filter tested successfully separated these regimes because gold was already in a daily golden cross (EMA50 > EMA200) even during the ranging period — it's a secular bull market.
- **Daily ADX filter made performance worse** — too correlated with the hourly ADX already in use.
- **Weekly EMA50 regime had no effect** — insufficient warmup with Jan 2022 data start.
- **Daily EMA50 vs EMA200 filter had no effect** — gold's secular bull means EMA50 > EMA200 during ranging periods too.
- **Optimal risk for pullback XAUUSD:** 0.4% per trade. Raising to 0.5% would push worst-case OOS DD to ~10.3% (breaches FTMO limit).

## Risk Guards

`DailyLossGuard`: tracks cumulative PnL per calendar day; blocks new signals once daily loss ≥ 5% of initial balance.

`MaxLossGuard`: tracks total drawdown; blocks all signals once total loss ≥ 10% of initial balance.

In `--research` mode both guards are disabled so the full period's performance is visible.

## Reports

All backtest outputs go to `reports/strategy_reports/`. JSON contains full metrics + `trade_pnls` list. CSV contains the trade log. Walk-forward validation saves `{SYMBOL}_{STRATEGY}_{TF}_validation.json` with per-window results, WFE, Monte Carlo, and verdict.

## Skills Available

Skills in `skills/` are prompt templates for specific research tasks:
- `review_backtest_results.md` — structured critique of a backtest (red flags: PF>3 with few trades, WR>70% with RR<1, DD>8%, IS→OOS degradation >30%)
- `generate_strategy_spec.md` — converts a trading idea into a testable spec
- `compare_experiments.md` — side-by-side comparison of parameter sweeps
- `build_feature_pipeline.md` — scaffolds a new feature/indicator

When reviewing backtest results, always check: PF stability IS→OOS, per-window OOS consistency, Monte Carlo P(DD>10%), and whether trade count is statistically sufficient (≥30 trades per period).
