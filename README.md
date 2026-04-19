# Trading Research Lab

Laboratorio unificado para investigación, backtesting, validación y evolución de estrategias de trading en forex, metales y crypto, con foco en pruebas de fondeo tipo FTMO.

## Filosofía

| Componente | Rol |
|---|---|
| **LEAN** | Framework principal de estrategia y validación |
| **Freqtrade** | Laboratorio crypto |
| **ML for Trading** | Research y diseño de señales/filtros |
| **MCP/Skills** | Productividad y asistencia al desarrollo |

## Flujo de trabajo

```
idea → spec → research → backtest → validación → reporte → decisión
```

## Setup rápido

```bash
cp .env.example .env
pip install -e ".[dev]"
```

## Estructura

```
trading-research-lab/
├── src/            # Código reutilizable (features, signals, risk, metrics, validation)
├── lean/           # Algoritmos QuantConnect/LEAN
├── freqtrade/      # Estrategias y configuraciones Freqtrade
├── notebooks/      # Exploración y research
├── docs/           # Documentación del proyecto
├── config/         # Configuraciones de activos, brokers, riesgo
├── prompts/        # Prompts reutilizables para asistentes IA
├── skills/         # Skills para Claude Code
└── mcp/            # Configuración de servidores MCP
```

## Activos iniciales

| Categoría | Activos |
|---|---|
| Forex | EURUSD, GBPUSD, USDJPY, EURJPY |
| Metales | XAUUSD |
| Crypto | BTCUSDT, ETHUSDT |

Orden de prioridad: XAUUSD → EURUSD → USDJPY → GBPUSD → BTC/ETH

## Familias de estrategias

1. **Breakout filtrado** — sesiones London/NY, filtro tendencia H1/H4, ADX/ATR mínimos
2. **Pullback en tendencia** — tendencia HTF, retroceso controlado, SL estructural
3. **Mean reversion filtrada** — rango claro, volatilidad moderada, filtro horario

## Estándares de validación FTMO

- Profit Factor >= 1.3
- Max Drawdown controlado
- Consistencia mensual
- Tolerancia a spreads/slippage peores
- Sin exceder pérdida diaria ni máxima simulada

Ver `docs/ftmo_rules.md` para el detalle completo.
