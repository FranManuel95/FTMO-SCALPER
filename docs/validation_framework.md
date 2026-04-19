# Framework de Validación

## Por qué validar así

Una estrategia con buen backtest IS (in-sample) puede ser solo curve-fitting.
El objetivo es detectar edge real antes de arriesgar capital en fondeo.

## Etapas de validación

### 1. In-Sample (IS)
- Período: 70% de los datos disponibles
- Objetivo: confirmar que existe algún edge bruto
- Umbral mínimo: PF >= 1.2, al menos 30 trades

### 2. Out-of-Sample (OOS)
- Período: 30% restante (nunca visto durante desarrollo)
- Objetivo: confirmar que el edge no desaparece
- Umbral mínimo: PF >= 1.1 (degradación aceptable <= 20%)

### 3. Walk-Forward (WF)
- Ventana de entrenamiento: 6 meses
- Ventana de test: 1 mes
- Paso: 1 mes
- Objetivo: estabilidad temporal del edge

### 4. Stress Tests
- Spread 2x: multiplicar spread por 2
- Spread 3x: multiplicar spread por 3
- Slippage adicional: añadir 0.5-1 pip de slippage extra
- Objetivo: estrategia no colapsa con condiciones peores

### 5. Monte Carlo
- N simulaciones: 1000
- Shuffling de trades
- Objetivo: distribución de drawdowns, probabilidad de ruina

### 6. FTMO Check
- Simular reglas de pérdida diaria y máxima
- Contar cuántas veces se hubiera violado la regla
- Objetivo: 0 violaciones o tasa < 5%

## Criterios de aceptación

| Check | Mínimo | Objetivo |
|---|---|---|
| Profit Factor IS | 1.2 | 1.5 |
| Profit Factor OOS | 1.1 | 1.3 |
| Degradación IS→OOS | < 25% | < 15% |
| Win Rate (con RR 1:2) | > 35% | > 40% |
| Max Drawdown | < 10% | < 7% |
| Sharpe Ratio | > 0.8 | > 1.2 |
| Violaciones FTMO | < 5% runs | 0% |
| WF Efficiency | > 0.5 | > 0.7 |

## Decisión final

- **PASS**: Cumple todos los mínimos → candidata para demo/fondeo
- **CONDITIONAL**: Cumple mínimos pero no objetivos → más research necesario
- **FAIL**: No cumple mínimos → descartar o rediseñar desde hipótesis

## Archivos relacionados

- `src/validation/in_sample.py`
- `src/validation/out_of_sample.py`
- `src/validation/walk_forward.py`
- `src/validation/monte_carlo.py`
- `src/validation/stress_tests.py`
- `src/metrics/ftmo_checks.py`
