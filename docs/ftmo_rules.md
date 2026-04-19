# Reglas FTMO — Referencia de Validación

## Challenge estándar FTMO

### Objetivos de profit
- Fase 1 (Challenge): +10% del capital
- Fase 2 (Verification): +5% del capital
- FTMO Account: sin objetivo de profit mínimo mensual

### Límites de pérdida
- **Pérdida diaria máxima**: 5% del capital inicial
- **Pérdida máxima total**: 10% del capital inicial

### Reglas de trading
- Mínimo 4 días de trading por fase
- Sin restricción de tiempo máximo por fase (en la versión estándar)
- Los trades deben cerrarse antes del fin de semana (depende del broker)

## Cómo simulamos estos límites en backtesting

```python
# Ejemplo de checks en src/metrics/ftmo_checks.py

MAX_DAILY_LOSS_PCT = 0.05    # 5% del capital inicial
MAX_TOTAL_LOSS_PCT = 0.10    # 10% del capital inicial
MIN_TRADING_DAYS = 4
```

## Checklist de validación

### Obligatorio
- [ ] Nunca superar pérdida diaria del 5%
- [ ] Nunca superar pérdida total del 10%
- [ ] Profit Factor >= 1.3 (orientativo)
- [ ] Mínimo 4 días de trading activo
- [ ] Consistencia mensual (sin dependencia de 1-2 trades)

### Recomendado
- [ ] Win rate coherente con el RR objetivo
- [ ] Drawdown máximo < 7% (margen de seguridad antes del límite)
- [ ] Tolerancia a spreads 2x peores del backtest
- [ ] Sin operaciones en noticias de alto impacto
- [ ] Backtested en mínimo 1 año de datos

## Activos y spreads de referencia

| Activo | Spread típico | Spread stress |
|---|---|---|
| EURUSD | 0.7 pips | 2.0 pips |
| GBPUSD | 1.0 pips | 3.0 pips |
| USDJPY | 0.8 pips | 2.5 pips |
| XAUUSD | $0.25 | $0.75 |
| BTCUSDT | 0.05% | 0.15% |

## Notas importantes

- Los checks FTMO deben implementarse en `src/metrics/ftmo_checks.py`
- El `daily_loss_guard.py` en `src/risk/` debe activarse durante la ejecución
- Cada reporte de estrategia debe incluir la sección "Resultado FTMO Check"
