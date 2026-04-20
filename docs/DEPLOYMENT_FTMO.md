# Deployment en FTMO demo + Telegram

Guía paso a paso para lanzar el portfolio en tu cuenta FTMO demo con notificaciones Telegram.

## 1. Pre-requisitos

- **Windows** (Windows 10/11 o Windows Server VPS). MT5 Python API **solo funciona en Windows**.
- **MT5 terminal** con tu cuenta FTMO demo ya creada.
- **Python 3.11+** instalado en la misma máquina que MT5.
- **Bot de Telegram** ya creado (tienes el token y el chat_id).

Recomendación: **VPS Windows 24/7** (Contabo/Hetzner/TradingVPS). Un portátil apagado no opera. Si vas a dejarlo corriendo en local, mantén la máquina despierta con política de energía "Nunca apagar".

## 2. Instalación

En la máquina Windows, abre PowerShell:

```powershell
# Clona el repo
git clone <tu-repo> C:\ftmo-scalper
cd C:\ftmo-scalper

# Crea entorno virtual
python -m venv .venv
.\.venv\Scripts\activate

# Instala el paquete con la extra live (incluye MetaTrader5)
pip install -e ".[live]"
```

## 3. Credenciales MT5 (FTMO demo)

En el terminal MT5 abierto, ve a **File > Login to Trade Account**. Copia:
- **Login** (número de cuenta, p.ej. `1510123456`)
- **Password** (el Investor o Master password que te dio FTMO — necesitas el Master para trading)
- **Server** (p.ej. `FTMO-Demo`, `FTMO-Demo2`)

## 4. Bot de Telegram

Si ya tienes el bot creado con @BotFather necesitas solo dos cosas:

1. **Bot token** — te lo dio @BotFather cuando lo creaste. Formato: `123456789:ABCdefGhIjKlMnOpQrStUvWxYz`
2. **Chat ID** — el ID del chat donde quieres recibir las alertas. Para obtenerlo:
   - Envía un mensaje cualquiera al bot desde tu Telegram
   - Abre en navegador: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   - Busca `"chat":{"id":XXXXXX,...}` — ese número es tu chat_id

## 5. Configurar .env

```powershell
# Copia la plantilla
Copy-Item .env.example .env
notepad .env
```

Rellena solo estas 5 variables (el resto puedes dejarlo vacío):

```ini
MT5_LOGIN=1510123456
MT5_PASSWORD=tu_master_password
MT5_SERVER=FTMO-Demo
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=987654321
```

Cargar las variables en la sesión:
```powershell
# Si usas python-dotenv ya se carga solo al arrancar el módulo
# Si no, cárgalas manualmente:
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2]) } }
```

## 6. Smoke test (sin enviar órdenes)

```powershell
# Dry-run con MT5 real pero sin enviar órdenes a FTMO — solo valida plumbing
python -m src.live.run_live --dry-run --once
```

Deberías ver en Telegram:
```
[FTMO] 🟢 Runner iniciado
Balance: 10000.00
Estrategias: xauusd_pullback_1h, gbpusd_pullback_1h, usdjpy_pullback_1h, xauusd_ny_orb_15m, xauusd_london_orb_15m
```

Si no llega nada, revisa que `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` están bien y que le has enviado al menos un `/start` al bot.

## 7. Ejecución real en FTMO demo

```powershell
python -m src.live.run_live --live --confirm "I UNDERSTAND"
```

El runner:
- Abre conexión al terminal MT5
- Cada 30s descarga barras cerradas y ejecuta las 5 estrategias
- Al primer cierre de barra que genera señal, envía orden market a FTMO
- Notifica por Telegram: señal detectada → orden abierta → cierre con PnL
- Actualiza trailing stops ATR cada tick

## 8. Qué esperar en los primeros días

- **0–3 días**: probablemente 0–2 trades. Las estrategias pullback 1H tienen ~1–2 señales/semana por par.
- **Primera semana**: 3–8 trades. Mezcla de ORBs 15m (más frecuentes) con pullbacks 1H.
- **Balance objetivo demo**: +1–3% al mes según backtest. Si en 3 semanas no hay ningún trade hay algo roto (MT5 no sincroniza barras, timezone incorrecta, filtros demasiado restrictivos).

## 9. Operativa diaria

Lo que recibirás en Telegram:

| Evento | Icono |
|---|---|
| Arranque | 🟢 Runner iniciado |
| Señal detectada | 📡 Señal |
| Orden ejecutada | 🟢 ORDEN ABIERTA |
| Posición cerrada + | ✅ CIERRE |
| Posición cerrada − | 🔴 CIERRE |
| Guard activado | ⛔ GUARD |
| Error | ⚠️ Error |

## 10. Seguridad y mantenimiento

- **Nunca** commitees `.env`. Está en `.gitignore`.
- **DailyLossGuard** bloquea nuevas señales cuando pierdes 5% en el día (pero no cierra las abiertas).
- **MaxLossGuard** bloquea todo cuando el drawdown total llega a 10%.
- **Para el runner**: Ctrl+C. El `disconnect()` se ejecuta en el `finally`.
- **Después de FTMO Phase 1 aprobada**: pasar a cuenta real con el mismo código cambiando solo `MT5_LOGIN / MT5_SERVER`.

## 11. Troubleshooting

| Síntoma | Causa habitual |
|---|---|
| `MT5 initialize failed` | Terminal cerrado o credenciales mal |
| No llegan mensajes Telegram | No has hecho `/start` al bot, o chat_id mal |
| No se generan señales en días de trading | Timezone del broker distinto a UTC+2, revisar `tz_offset_hours` |
| Órdenes rechazadas (retcode ≠ `TRADE_RETCODE_DONE`) | Volumen mínimo del broker, stops demasiado cerca, horario cerrado |
