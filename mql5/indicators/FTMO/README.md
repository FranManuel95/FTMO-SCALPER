# Indicadores MT5 — Visualizadores de las estrategias

Tres custom indicators que muestran las señales del bot directamente en charts de MT5.

| Archivo | Qué hace |
|---|---|
| `FTMO_Pullback.mq5` | Familia Trend Pullback (XAUUSD, USDJPY, GBPUSD, AUDUSD). EMA20/EMA50, flechas en pullbacks válidos, panel de filtros. |
| `FTMO_ORB.mq5` | Las 14 estrategias ORB (Asian/London/NY). Caja sombreada del rango, flechas en breakouts, ventana de entrada visible. |
| `FTMO_TrailViewer.mq5` | Sobre cualquier posición abierta del bot, dibuja entry/SL/TP en vivo + trail teórico para comparar con lo que está aplicando el bot. |

## Instalación

1. Localiza la carpeta de datos de MT5:
   - En MT5: **Archivo → Abrir carpeta de datos**
   - Se abre `C:\Users\TU_USUARIO\AppData\Roaming\MetaQuotes\Terminal\<HASH>\`

2. Copia los 3 `.mq5` a `MQL5\Indicators\FTMO\` (crea la carpeta `FTMO`)

3. Abre **MetaEditor** (F4 en MT5)

4. En el árbol de la izquierda: `Indicators → FTMO`. Doble clic en cada `.mq5` y pulsa **F7** (compilar).
   Debe terminar con `0 errors, 0 warnings`. Verás aparecer el `.ex5` correspondiente.

5. En MT5: **Navigator → Indicators → Custom → FTMO**. Arrastra cualquiera al chart.

## Configuración por estrategia

### FTMO_Pullback

Inputs principales:

| Estrategia | AdxMin | LongOnly | RsiOver | RsiUnder |
|---|---|---|---|---|
| XAUUSD 1H Pullback | 25 | false | 60 | 40 |
| USDJPY 1H Pullback | 20 | false | 60 | 40 |
| GBPUSD 1H Pullback | 25 | false | 60 | 40 |
| AUDUSD 1H Pullback | 25 | **true** | 60 | 40 |

`AtrSlMult=1.5`, `RrTarget=2.5`, `UseH4Filter=true` para todos.

### FTMO_ORB — Tres presets

**Asian ORB** (USDJPY, EURJPY, GBPJPY, NZDUSD, AUDUSD, USDCAD, GBPUSD, USDCHF, EURUSD — todos en 1H):
```
RangeStartUTC = 23
RangeEndUTC   = 7
EntryStartUTC = 7
EntryEndUTC   = 12
AdxMin        = 18
AtrSlMult     = 0.1
RrTarget      = 2.5
```

**London ORB** (XAUUSD, EURUSD, USDCHF, EURGBP, GBPJPY — todos en 15M):
```
RangeStartUTC = 7
RangeEndUTC   = 8
EntryStartUTC = 8
EntryEndUTC   = 12
AdxMin        = 18
AtrSlMult     = 0.3
RrTarget      = 2.5
```

**NY ORB** (XAUUSD, USDCAD, GBPUSD — todos en 15M):
```
RangeStartUTC = 13
RangeEndUTC   = 14
EntryStartUTC = 14
EntryEndUTC   = 20
AdxMin        = 18
AtrSlMult     = 0.5
RrTarget      = 2.5
```

### FTMO_TrailViewer

`BotMagic = 90210` (no cambiar — es el magic del bot).

`TrailAtrMult` — ajusta al trail que use la estrategia que estés viendo:
- Asian ORB: 0.2
- London ORB: 0.3 (XAUUSD, EURGBP) o 0.4 (GBPJPY) o 0.5 (EURUSD, USDCHF)
- NY ORB: 0.4 (USDCAD, GBPUSD) o 0.5 (XAUUSD)
- Pullback: 0.2 (USDJPY) o 0.3 (XAUUSD, AUDUSD) o 0.5 (GBPUSD)

## Importante

- **El indicador NO opera**, solo visualiza. No interfiere con el bot.
- Las flechas son señales TEÓRICAS sin filtro `DailyLossGuard` ni `MaxLossGuard`. Si el bot estaba bloqueado por DD diario, en el chart verás la flecha pero el bot NO entró.
- Las flechas tampoco aplican la regla "una posición abierta por estrategia". Si el bot ya tenía un trade abierto, ignora la nueva señal aunque la flecha aparezca.
- Por eso ves el indicador como mapa de **dónde habría señales válidas a nivel de motor**, no de "trades reales". Para reales, mira el dashboard o el `events.db`.
- Las cajas de rango (ORB) se redibujan al cargar el indicador con MaxDaysBack=60 días por defecto. Para meses/años atrás, sube el valor.

## Tips operativos

1. **Para entender la lógica:** carga `FTMO_ORB.mq5` con preset London sobre **XAUUSD M15**, ve al pasado con la barra de tiempo y observa cómo se construyen los rangos cada día y dónde aparecen los breakouts.

2. **Para vigilar en vivo:** carga `FTMO_TrailViewer.mq5` sobre el chart del símbolo donde ves una posición abierta en MT5. Las líneas de SL/TP se actualizan en tiempo real cuando el bot mueve el trail. La línea dorada discontinua muestra dónde "debería" estar el trail según la fórmula — si las dos coinciden, el bot está aplicando el trail correctamente.

3. **Strategy Tester:** los 3 indicadores funcionan también dentro del Strategy Tester de MT5 (modo "indicadores nativos"). Útil para revisar 1 año de gráficos paso a paso.

## Diferencias esperadas vs el bot

Los indicadores deberían coincidir 99%+ con el bot. Diferencias menores conocidas:
- **Una posición abierta por estrategia:** el bot ignora señales nuevas si ya tiene un trade, el indicador no.
- **DailyLossGuard / MaxLossGuard:** el bot deja de operar tras tocar -5% diario o -10% total. El indicador siempre dibuja flechas.
- **Frecuencia de tick:** el bot evalúa cada 30s; el indicador en cada tick.

Si ves una flecha donde el bot NO operó: revisa si había guard activo, o si ya había trade abierto en esa estrategia. Si pasa frecuentemente sin razón obvia, dilo y lo investigamos.
