# Skill: review_backtest_results

## Propósito
Analiza críticamente un resultado de backtest y genera recomendaciones concretas.

## Input esperado
Resultados en JSON o tabla con métricas: PF, WR, DD, Sharpe, trades, curva de equity.

## Análisis que genera

### Red flags automáticos
- PF muy alto (>3.0) con pocos trades → posible overfitting
- Win rate > 70% con RR < 1:1 → frágil estadísticamente
- Todos los trades concentrados en 1-2 meses → no generalizable
- DD máximo > 8% → peligroso para FTMO
- Degradación IS→OOS > 30% → señal de curve-fitting

### Fortalezas detectables
- PF estable entre IS y OOS
- Win rate coherente con RR
- Distribución de trades uniforme en el tiempo
- Múltiples meses profitables
- Resiste stress tests básicos

### Output estructurado
1. **Veredicto**: PASS / CONDITIONAL / FAIL
2. **Confianza en el edge**: Alta / Media / Baja
3. **Principal riesgo**: [descripción]
4. **Siguiente paso recomendado**: [acción concreta]

## Instrucciones de uso

```
Usa la skill review_backtest_results con estos resultados:
[pegar JSON o tabla de resultados]
```
