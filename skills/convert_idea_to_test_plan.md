# Skill: convert_idea_to_test_plan

## Propósito
Convierte una intuición o setup en un plan de backtest ejecutable mínimo.

## Input esperado
Una idea vaga o una observación de mercado:
> "Noto que el EURUSD tiene momentum fuerte los lunes por la mañana"

## Output generado

### Plan de backtest mínimo

**Hipótesis a testear:**
> [Formulación testeable]

**Activos:**
- Principal: [activo]
- Secundarios (para robustez): [activos]

**Timeframes:**
- Análisis: [TF para contexto]
- Entrada: [TF para señal]

**Período:**
- IS: [fechas]
- OOS: [fechas]

**Grid inicial (pequeño):**
| Parámetro | Valores a testear |
|---|---|
| param1 | [3-5 valores máximo] |

**Métricas de aceptación:**
- PF IS >= 1.2
- PF OOS >= 1.1
- Trades >= 30
- DD < 10%

**Riesgo de overfitting a controlar:**
- [Qué no optimizar en primera vuelta]

**Tiempo estimado:**
- Research: X horas
- Implementación: X horas
- Backtest + análisis: X horas

## Instrucciones de uso

```
Usa la skill convert_idea_to_test_plan para la siguiente intuición:
[tu observación aquí]
```
