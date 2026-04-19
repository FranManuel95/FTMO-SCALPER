# Skill: generate_strategy_spec

## Propósito
Convierte una idea de trading en una especificación estructurada lista para backtesting.

## Cuándo usar
Cuando tienes una intuición de mercado o un setup que quieres formalizar antes de codificar.

## Input esperado
Una descripción informal de la idea:
> "El oro suele subir fuerte en la apertura de Londres cuando hay compresión asiática"

## Output generado

### 1. Hipótesis formal
> "Cuando el rango asiático de XAUUSD es inferior al ATR(14) del día anterior y el precio abre London
> por encima del 60% del rango asiático, existe sesgo alcista en las primeras 2 horas de London."

### 2. Condiciones de entrada
- Contexto: [condición HTF obligatoria]
- Setup: [condición de preparación]
- Trigger: [vela/precio específico que activa]
- Invalidación: [condición que cancela el setup]

### 3. Condiciones de salida
- SL: [descripción con lógica, no solo número]
- TP: [objetivo y ratio RR mínimo]
- Time exit: [si aplica]
- Trailing: [si aplica]

### 4. Parámetros a testear
| Parámetro | Tipo | Rango sugerido | Default |
|---|---|---|---|
| adx_min | float | 18-28 | 22 |

### 5. Activos y timeframes sugeridos
- Principal: [activo y TF]
- Adicionales: [para confirmar robustez]

### 6. Riesgos y debilidades esperadas
- [Riesgo 1: ej. funciona solo en tendencia, falla en rango]
- [Riesgo 2: ej. spread alto en news puede distorsionar entrada]

### 7. Criterios de aceptación mínimos
- PF IS >= X
- PF OOS >= X
- Max DD < X%
- N trades >= X

## Instrucciones de uso

Pega esta skill en Claude con tu idea:

```
Usa la skill generate_strategy_spec para la siguiente idea:
[tu idea aquí]
```
