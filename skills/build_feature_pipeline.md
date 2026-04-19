# Skill: build_feature_pipeline

## Propósito
Convierte una lista de ideas de features en un pipeline estructurado con advertencias de data leakage.

## Input esperado
Lista de features o filtros que se quieren usar:
> "quiero usar ADX, ATR, rango asiático, hora del día y pendiente de EMA"

## Output generado

### Pipeline de features propuesto

| Feature | Tipo | Cálculo | Lookback | Riesgo leakage |
|---|---|---|---|---|
| ADX(14) | técnico | ta.adx() | 14 velas | bajo |
| ATR(14) | volatilidad | ta.atr() | 14 velas | bajo |
| asian_range | sesión | high-low 00-07 UTC | sesión anterior | medio* |

*Nota: usar siempre la sesión asiática del día ANTERIOR, nunca la del día actual.

### Advertencias de data leakage detectadas
- [Advertencia 1: ej. asian_range del día actual filtra información futura]
- [Advertencia 2: ej. EMA calculada con close de la misma vela de entrada]

### Hipótesis de utilidad de cada feature
- ADX: [por qué debería ayudar en esta estrategia]
- ATR: [por qué debería ayudar]

### Features recomendadas para empezar
[Subconjunto mínimo más robusto]

### Features a probar en segunda iteración
[Features más complejas o con más riesgo de overfitting]

## Instrucciones de uso

```
Usa la skill build_feature_pipeline con estas ideas de features:
[lista de features/filtros]
Contexto: [estrategia y activo para el que son]
```
