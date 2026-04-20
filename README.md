# FTMO Scalper

Sistema de trading automático para cuentas de fondeo FTMO. Incluye investigación, backtesting, validación walk-forward y ejecución live en MetaTrader 5.

## Estrategias validadas (walk-forward 6/6 OOS)

| Estrategia | Par / TF | OOS PF | DD p95 | Risk/trade |
|---|---|---|---|---|
| Trend Pullback | XAUUSD 1H | 5.55 | 1.6% | 0.4% |
| Trend Pullback | GBPUSD 1H | 2.82 | 1.9% | 0.4% |
| Trend Pullback | USDJPY 1H | 2.52 | 1.8% | 0.3% |
| NY Open ORB | XAUUSD 15M | 4.21 | 0.6% | 0.25% |
| London Open ORB | XAUUSD 15M | 2.91 | 0.5% | 0.25% |
| Asian Session ORB | USDJPY 1H | **24.89** | 0.5% | 0.3% |
| Trend Pullback | NZDUSD 1H | 2.40 | 1.5% | 0.3% |
| Trend Pullback (L) | AUDUSD 1H | 5.76 | 0.2% | 0.3% |
| Fair Value Gap | XAUUSD 1H | 1.57 | 3.2% | 0.2% |

Todas usan trailing stop ATR. Validadas con IS=12m / OOS=6m, periodo 2022–2026.

## Instalación

```bash
# Linux / dev / CI
pip install -e ".[dev]"

# Windows (trading live)
pip install -e ".[live]"   # incluye MetaTrader5
```

## Trading live (Windows + MT5)

```bash
# Copia y rellena credenciales
cp .env.example .env
notepad .env   # MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, TELEGRAM_*

# Diagnóstico completo
python -m src.live.run_live --check

# Dry-run (sin enviar órdenes)
python -m src.live.run_live --dry-run --once

# Live real
python -m src.live.run_live --live --confirm "I UNDERSTAND"
```

Ver guía completa en [`docs/DEPLOYMENT_FTMO.md`](docs/DEPLOYMENT_FTMO.md).

## Research loop (nueva estrategia)

```bash
# 1. Crea spec
cp config/strategies/xauusd_pullback_1h.yaml config/strategies/mi_estrategia.yaml

# 2. Corre pipeline IS → OOS → Walk-Forward automático
python -m src.orchestration.run_research_loop --spec config/strategies/mi_estrategia.yaml
```

## Estructura

```
src/
├── signals/          # Generadores de señales (pullback, breakout)
├── features/         # Indicadores técnicos (ATR, ADX, EMA, HTF)
├── risk/             # DailyLossGuard, MaxLossGuard, position sizing
├── live/             # Runner MT5: MT5Client, OrderManager, TrailManager,
│                     #             PortfolioRunner, TelegramNotifier
├── orchestration/    # run_backtest, run_validation, run_combined
└── core/             # Tipos base (Signal, Side, SignalType)

config/strategies/    # Specs YAML por estrategia
backtest/data/        # CSVs MT5 (XAUUSD, GBPUSD, USDJPY... 2022–2026)
reports/              # Resultados backtests y validaciones
docs/                 # Arquitectura, reglas FTMO, deployment
```

## Tests

```bash
pytest tests/test_live_runner.py -v   # live module
pytest --no-cov -q                    # suite completa
```

## Reglas FTMO (cuenta €10k)

| Regla | Límite | Sistema |
|---|---|---|
| Pérdida diaria | -5% (-€500) | DailyLossGuard |
| Pérdida máxima | -10% (-€1000) | MaxLossGuard |
| Objetivo Phase 1 | +10% (+€1000) | ~3–4 meses |
| Objetivo Phase 2 | +5% (+€500) | ~1–2 meses |
