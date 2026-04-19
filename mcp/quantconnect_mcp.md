# MCP — QuantConnect / LEAN

## Qué permite

Con un MCP de QuantConnect un agente puede:
- Crear y modificar algoritmos LEAN
- Lanzar backtests en la nube
- Revisar resultados de backtests
- Navegar la librería de datos de QC
- Interactuar con el Research Environment

## Setup (lean-cli)

```bash
pip install lean
lean login
lean init
```

## Workflow típico con LEAN CLI

```bash
# Crear nuevo algoritmo
lean create-project "MyAlgorithm"

# Backtesting local
lean backtest "MyAlgorithm"

# Research notebook
lean research "MyAlgorithm"

# Cloud backtest
lean cloud push --project "MyAlgorithm"
lean cloud backtest "MyAlgorithm"
```

## Estructura en este proyecto

```
lean/
├── algorithms/
│   ├── forex/          # Algoritmos C# o Python para forex
│   ├── metals/         # XAUUSD y otros metales
│   └── crypto/         # BTC, ETH
├── research/           # Notebooks de research QC
└── config/
    └── lean.json       # Configuración local LEAN
```

## Conexión con src/

Los algoritmos LEAN en `lean/algorithms/` pueden importar lógica de `src/`
usando adaptadores. Ver `freqtrade/adapters/` como referencia de patrón.
