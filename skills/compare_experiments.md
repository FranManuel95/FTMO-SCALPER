# Skill: compare_experiments

## Propósito
Compara múltiples experimentos de la misma estrategia o estrategias diferentes y genera un ranking.

## Input esperado
Lista de resultados de experimentos (JSON o tabla comparativa).

## Output generado

### Ranking de experimentos
| # | Experimento | PF IS | PF OOS | DD | Sharpe | FTMO | Score |
|---|---|---|---|---|---|---|---|
| 1 | exp_name | 1.8 | 1.5 | 6% | 1.4 | PASS | 82 |

### Análisis de robustez
- ¿Qué configuraciones son estables entre IS y OOS?
- ¿Hay parámetros que claramente mejoran o empeoran resultados?
- ¿El mejor experimento IS es también el mejor OOS?

### Qué conservar
- [Reglas o features que aparecen en todos los buenos experimentos]

### Qué descartar
- [Parámetros que crean overfitting o son inestables]

### Recomendación
- **Mejor candidato**: [experimento con razonamiento]
- **Siguiente iteración**: [qué probar basado en los hallazgos]

## Instrucciones de uso

```
Usa la skill compare_experiments con los siguientes resultados:
[pegar resultados de experimentos]
```
