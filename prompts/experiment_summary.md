# Prompt: Experiment Summary

Genera un resumen ejecutivo estandarizado para el siguiente experimento de trading:

Estrategia: {strategy_name}
Activo: {symbol}
Período: {period}
Timeframe: {timeframe}

Resultados:
```
{results_json}
```

El resumen debe incluir:

## Resumen ejecutivo (3-4 líneas)
[Descripción breve del resultado: funcionó/no funcionó, por qué]

## Métricas clave
| Métrica | Valor | Benchmark |
|---|---|---|
| Profit Factor | X | >= 1.3 |
| Win Rate | X% | coherente con RR |
| Max Drawdown | X% | < 10% |
| Sharpe | X | >= 1.0 |
| FTMO Check | PASS/FAIL | PASS |

## Hallazgos principales
1. [Hallazgo 1]
2. [Hallazgo 2]
3. [Hallazgo 3]

## Decisión
- [ ] Continuar desarrollo
- [ ] Congelar (revisar más adelante)
- [ ] Descartar

## Siguiente iteración propuesta
[Si continúa, qué cambiar específicamente]
