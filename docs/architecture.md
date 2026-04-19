# Arquitectura del Sistema

## Capas del sistema

```
┌─────────────────────────────────────────────────────┐
│                  Orchestration                       │
│  run_research | run_backtest | run_validation        │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                   Signals                            │
│  breakout | pullback | mean_reversion | trend        │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                  Features                            │
│  technical | volatility | session | trend | regime   │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│                    Data                              │
│       loaders | cleaners | resamplers | validators   │
└─────────────────────────────────────────────────────┘
```

## Flujo de datos

```
Fuente externa (OANDA, Binance, Yahoo)
       ↓
  data/loaders  →  data/raw/
       ↓
  data/cleaners + resamplers  →  data/processed/
       ↓
  src/features  →  feature matrix
       ↓
  src/signals   →  señales de entrada/salida
       ↓
  src/risk      →  filtros de riesgo y sizing
       ↓
  src/execution →  gestión de trade (SL/TP/BE/trailing)
       ↓
  src/metrics   →  evaluación de resultados
       ↓
  src/validation →  IS/OOS/WF/stress
       ↓
  reports/      →  reporte final
```

## Dependencias entre módulos

- `signals` depende de `features`
- `features` depende de `data`
- `risk` es independiente (recibe posición, retorna size/go-no-go)
- `execution` depende de `risk`
- `metrics` es independiente (recibe trades, retorna estadísticas)
- `validation` depende de `metrics`
- `orchestration` coordina todo

## Integraciones externas

```
LEAN ←→ src/signals (algoritmos en lean/algorithms/)
Freqtrade ←→ src/signals (estrategias en freqtrade/user_data/strategies/)
```

Ambas integraciones son adaptadores: la lógica core vive en `src/`, los adaptadores
la envuelven para cada framework.
