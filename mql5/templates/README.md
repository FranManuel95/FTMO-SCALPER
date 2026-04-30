# Plantillas MT5 (`.tpl`)

5 plantillas pre-configuradas con los inputs correctos para cada familia de estrategias.

## Instalación (una sola vez)

1. En MT5 abre **Archivo → Abrir carpeta de datos** → te abre `...\Terminal\<HASH>\`
2. Ve a `MQL5\Profiles\Templates\` (créala si no existe)
3. Copia los 5 archivos `.tpl` desde `C:\ftmo-scalper\mql5\templates\` a esa carpeta

## Uso

En cualquier chart, click derecho → **Plantilla** → elige la plantilla:

| Plantilla | Para qué sirve |
|---|---|
| `FTMO_Pullback_H1` | Estrategias Trend Pullback (XAUUSD, USDJPY, GBPUSD, NZDUSD) |
| `FTMO_ORB_London_M15` | Las 5 London ORBs (XAUUSD, EURUSD, USDCHF, EURGBP, GBPJPY) |
| `FTMO_ORB_NY_M15` | Las 3 NY ORBs (XAUUSD, USDCAD, GBPUSD) |
| `FTMO_ORB_Asian_H1` | Las 9 Asian ORBs (USDJPY, EURJPY, GBPJPY, AUDUSD, NZDUSD, USDCAD, GBPUSD, EURUSD, USDCHF) |
| `FTMO_TrailViewer` | Vigilar trail SL en posiciones abiertas del bot |

## Importante: ajustes finales por par

Las plantillas tienen valores por defecto que cubren la mayoría. Para cada par hay que ajustar 1-2 inputs concretos:

### `FTMO_Pullback_H1`
Por defecto `AdxMin=25, LongOnly=false`. Para casos especiales:

| Par | AdxMin | LongOnly |
|---|---|---|
| XAUUSD | 25 | false |
| GBPUSD | 25 | false |
| **USDJPY** | **20** | false |
| **NZDUSD** | **22** | false |

### `FTMO_ORB_London_M15`
Por defecto `AtrSlMult=0.3` (XAUUSD/EURGBP). Ajustar:

| Par | AtrSlMult |
|---|---|
| XAUUSD | **0.3** |
| EURGBP | **0.3** |
| EURUSD | **0.5** |
| USDCHF | **0.4** |
| GBPJPY | **0.4** |

### `FTMO_ORB_NY_M15`
Por defecto `AtrSlMult=0.5` (XAUUSD). Ajustar:

| Par | AtrSlMult |
|---|---|
| XAUUSD | **0.5** |
| USDCAD | **0.4** |
| GBPUSD | **0.4** |

### `FTMO_ORB_Asian_H1`
Por defecto `AtrSlMult=0.1` (mismo para todas). No requiere ajuste por par.

### `FTMO_TrailViewer`
Por defecto `TrailAtrMult=0.3`. Ajusta al trail real de la estrategia que estés viendo:

| Familia | TrailAtrMult |
|---|---|
| Pullback XAUUSD/AUDUSD/NZDUSD | 0.3-0.4 |
| Pullback USDJPY | 0.2 |
| Pullback GBPUSD | 0.5 |
| London ORB XAUUSD/EURGBP | 0.3 |
| London ORB EURUSD | 0.5 |
| London ORB USDCHF/GBPJPY | 0.4 |
| NY ORB XAUUSD | 0.5 |
| NY ORB USDCAD/GBPUSD | 0.4 |
| Asian ORB (todos JPY+resto) | 0.2-0.3 |

## Cómo cambiar los inputs tras cargar plantilla

1. Click derecho sobre el indicador (cualquier flecha o línea) → **Indicador → Editar**
2. Pestaña **Inputs** → cambia el valor que toque (ej: `AtrSlMult` de 0.3 a 0.5)
3. OK

Si quieres guardar el ajuste como NUEVA plantilla específica:
- Click derecho en chart → **Plantilla → Guardar plantilla** → nombre tipo `FTMO_ORB_London_EURUSD`

## Si la plantilla falla al cargar

MT5 puede ser quisquilloso con el formato `.tpl`. Si te sale "Error al leer plantilla" o el indicador no aparece:

1. Borra la plantilla del Templates folder
2. En un chart, configura UN indicador a mano con los inputs correctos
3. Click derecho → Plantilla → **Guardar plantilla** → con el nombre que toque
4. Esa plantilla guardada por MT5 funciona seguro (es la versión "canónica" de tu broker)
