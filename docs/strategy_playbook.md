# Strategy Playbook

Registro de todas las estrategias en investigación, desarrollo y producción.

## Template de entrada

```markdown
## [NOMBRE_ESTRATEGIA]

- **Mercado**: EURUSD / XAUUSD / BTCUSDT / ...
- **Timeframe**: M15 / H1 / H4 / ...
- **Familia**: breakout / pullback / mean_reversion / trend_following
- **Estado**: idea / en_research / backtesting / validando / activa / congelada

### Hipótesis
[Descripción de por qué debería funcionar]

### Contexto de mercado requerido
- Tendencia HTF: [condición]
- Volatilidad: [condición]
- Sesión: [London / NY / Asia / any]

### Reglas de entrada
1. [Condición 1]
2. [Condición 2]
3. [Trigger de entrada]

### Reglas de salida
- SL: [descripción]
- TP: [descripción]
- Trailing: [si aplica]
- Time exit: [si aplica]

### Parámetros a testear
| Parámetro | Rango | Default |
|---|---|---|
| adx_min | 20-30 | 25 |

### Resultados IS
[Pendiente]

### Resultados OOS
[Pendiente]

### Veredicto
[Pendiente]
```

---

## Estrategias registradas

### XAUUSD Breakout London — v1

- **Mercado**: XAUUSD
- **Timeframe**: M15
- **Familia**: breakout
- **Estado**: idea

### Hipótesis
El oro tiende a tener breakouts significativos en la apertura de Londres (07:00-09:00 UTC),
especialmente cuando hay compresión asiática previa y ADX > 20 en H1.

### Contexto de mercado requerido
- Tendencia HTF: H4 alcista o bajista definida (no lateral)
- Volatilidad: ATR H1 > umbral mínimo
- Sesión: apertura London (07:00-09:00 UTC)

### Reglas de entrada
1. Identificar rango asiático (00:00-07:00 UTC)
2. Esperar breakout confirmado del rango
3. Validar con cierre de vela M15 fuera del rango
4. ADX H1 > 20
5. Entrar al cierre de la vela de breakout

### Reglas de salida
- SL: Por debajo/encima del rango asiático + buffer ATR
- TP: 2x SL (RR 1:2 mínimo)
- Time exit: Cerrar si no alcanza TP antes de 12:00 UTC

### Parámetros a testear
| Parámetro | Rango | Default |
|---|---|---|
| adx_min | 18-28 | 22 |
| atr_min_mult | 0.5-1.5 | 1.0 |
| rr_target | 1.5-3.0 | 2.0 |
| asian_session_end | 06:00-08:00 | 07:00 |
