# FTMO Scalper — Dashboard de observabilidad

Dashboard Streamlit para visualizar el comportamiento del bot live en tiempo real.

## Qué muestra

| Página | Pregunta que responde |
|---|---|
| **📊 Overview** | ¿Cómo está la cuenta AHORA? Balance, equity, FTMO progress, posiciones abiertas, alertas |
| **🎯 Strategies** | ¿Cuáles estrategias funcionan? PF/WR/expectancy por estrategia, drift detector |
| **⚙️ Execution** | ¿Cómo de bien estamos ejecutando? Slippage por símbolo, quick-stop rate, latencias del runner |
| **📜 Trades** | ¿Qué pasó? Histórico filtrable, resumen diario, curva de equity |
| **🔍 Inspector** | ¿Qué pasó EXACTAMENTE con el ticket X? Timeline completa + gráfico SL/TP |
| **🚨 Anomalies** | ¿Hay algo raro? Detección automática de patrones sospechosos |

## Arquitectura

El bot escribe eventos estructurados a dos sitios:

```
data/
  events.db       # SQLite indexado (queryable, lo lee el dashboard)
  events.jsonl    # Append-only durable (fuente de verdad, regenera SQLite si hace falta)
```

Tipos de eventos registrados:

- `strategy_tick` — cada ejecución de estrategia con latencias
- `signal` — cada señal (con `was_executed` y `filter_reason`)
- `guard_check` — daily/max loss guard activado
- `order` — orden enviada a MT5 con slippage real medido
- `trail_update` — cada evaluación de trail (aplicado o saltado, con motivo)
- `position_close` — cierre detectado con MFE/MAE y `close_reason` inferido
- `system_event` — bot start/stop, mt5 disconnect, position recovery
- `market_snapshot` — equity/balance cada minuto

El dashboard lee el SQLite en read-only mientras el bot escribe — sin contención.

## Ejecutar

### Instalación

```bash
pip install -e ".[dashboard]"
```

### Lanzar

```bash
./dashboard/run_dashboard.sh
# o directamente
streamlit run dashboard/app.py
```

Por defecto escucha en `http://localhost:8501`.

### Configuración

Variables de entorno opcionales:

- `FTMO_EVENTS_DB` — ruta del SQLite (default `data/events.db`)
- `FTMO_INITIAL_BALANCE` — balance inicial para cálculos FTMO (default 160000)
- `PORT` — puerto del dashboard (default 8501)

### Acceder remotamente

Si el bot corre en una máquina Windows y quieres ver el dashboard desde el portátil:

```bash
# En la máquina del bot:
./dashboard/run_dashboard.sh

# En tu portátil, túnel SSH:
ssh -L 8501:localhost:8501 user@windows-box

# Luego abrir http://localhost:8501 en el navegador local.
```

## Refresh automático

El Overview hace auto-refresh cada 30 segundos (configurable en sidebar).
Las demás páginas refrescan cuando se interactúa con sus filtros.

## Anomaly detection

El dashboard alerta automáticamente cuando:

- Una estrategia tiene > 50% de trades cerrando en < 5 min (posible falso breakout)
- Una estrategia lleva 4+ pérdidas consecutivas
- El slippage de un símbolo supera 2.5σ del histórico
- El lot size de un trade desvía > 3σ (posible bug de sizing)

Las alertas críticas aparecen también en el Overview.
