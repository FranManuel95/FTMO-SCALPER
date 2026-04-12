# config/settings.py — Configuración central del FTMO Scalper
# Todos los parámetros de riesgo, estrategia y broker en un único lugar.
# IMPORTANTE: No tocar los límites FTMO sin revisión. Son conservadores a propósito.

# ─────────────────────────────────────────────
# REGLAS FTMO (desafío estándar $10k)
# ─────────────────────────────────────────────
FTMO_DAILY_LOSS_LIMIT_PCT  = 0.045   # 4.5%  — FTMO permite 5%, usamos buffer del 0.5%
FTMO_MAX_DRAWDOWN_PCT      = 0.095   # 9.5%  — FTMO permite 10%, buffer del 0.5%
FTMO_PROFIT_TARGET_PCT     = 0.10    # 10%   — Objetivo del desafío
FTMO_MIN_TRADING_DAYS      = 10      # Mínimo días con al menos 1 operación
FTMO_MAX_TRADES_PER_DAY    = 8       # Límite conservador de operaciones/día

# ─────────────────────────────────────────────
# GESTIÓN DE RIESGO
# ─────────────────────────────────────────────
RISK_PER_TRADE_PCT   = 0.005   # 0.5% por trade — 20 trades para el 10% (con 100% WR)
MIN_RR_RATIO         = 1.6     # Mínimo relación riesgo/recompensa
NEWS_BLOCK_MINUTES   = 30      # Minutos bloqueados antes/después de noticias

# ─────────────────────────────────────────────
# SÍMBOLOS EN PRODUCCIÓN
# ─────────────────────────────────────────────
# Estrategia MTF EMA (London + NY sessions)
SYMBOLS_MTF    = ["EURUSD", "GBPUSD"]

# Estrategia Breakout (Asian range)
SYMBOLS_BREAKOUT = ["USDJPY", "EURJPY"]

# Estrategia ORB (Opening Range Breakout)
SYMBOLS_ORB    = ["XAUUSD"]

# Todos los símbolos activos
ALL_SYMBOLS    = SYMBOLS_MTF + SYMBOLS_BREAKOUT + SYMBOLS_ORB

# ─────────────────────────────────────────────
# SESIONES DE MERCADO (UTC)
# ─────────────────────────────────────────────
LONDON_OPEN   = (7, 0)    # 07:00 UTC
LONDON_CLOSE  = (17, 0)   # 17:00 UTC (solapamiento NY empieza a las 13:00)
NY_OPEN       = (13, 0)   # 13:00 UTC
NY_CLOSE      = (20, 0)   # 20:00 UTC
ASIAN_OPEN    = (0, 0)    # 00:00 UTC
ASIAN_CLOSE   = (7, 0)    # 07:00 UTC (coincide con apertura London)

# ─────────────────────────────────────────────
# INDICADORES — ESTRATEGIA MTF (EURUSD/GBPUSD)
# ─────────────────────────────────────────────
MTF_EMA_TREND   = 200    # EMA de tendencia en 1H
MTF_EMA_FAST    = 20     # EMA rápida en 15M
MTF_EMA_SLOW    = 50     # EMA lenta en 15M
MTF_EMA_ENTRY   = 9      # EMA de entrada en 5M
MTF_EMA_CONFIRM = 21     # EMA de confirmación en 5M
MTF_ADX_PERIOD  = 14
MTF_ADX_MIN     = 18     # Filtro: mínimo fuerza de tendencia
MTF_ADX_MAX     = 58     # Filtro: evitar tendencias sobreextendidas
MTF_RSI_PERIOD  = 14
MTF_ATR_PERIOD  = 14
MTF_ATR_SL_MULT = 1.2    # Stop Loss = ATR × 1.2
MTF_RR_RATIO    = 1.6    # Take Profit = SL × 1.6 (riesgo:recompensa)
MTF_ATR_MIN     = 0.0003 # ATR mínimo para operar (filtra baja volatilidad)
MTF_TRAIL_MULT  = 2.0    # Trailing stop = ATR × 2.0

# ─────────────────────────────────────────────
# INDICADORES — ESTRATEGIA BREAKOUT (USDJPY/EURJPY)
# ─────────────────────────────────────────────
BRK_ATR_PERIOD      = 14
BRK_ATR_SL_MULT     = 1.5
BRK_RR_RATIO        = 2.0
BRK_BUFFER_PIPS     = 0.04    # Buffer encima/debajo del rango asiático
BRK_MIN_BODY_RATIO  = 0.50    # La vela de ruptura debe tener ≥50% de cuerpo
BRK_MAX_HOLD_BARS   = 42      # Máximo de velas a mantener la posición

# ─────────────────────────────────────────────
# INDICADORES — ESTRATEGIA ORB (XAUUSD)
# ─────────────────────────────────────────────
ORB_WINDOW_OPEN    = (7, 0)   # Inicio construcción del rango de apertura
ORB_WINDOW_CLOSE   = (9, 0)   # Fin construcción del rango de apertura
ORB_TRADE_OPEN     = (9, 0)   # Inicio ventana de trading
ORB_TRADE_CLOSE    = (16, 0)  # Cierre ventana de trading
ORB_ATR_PERIOD     = 14
ORB_ATR_SL_MULT    = 1.2
ORB_RR_RATIO       = 2.0
ORB_BREAKEVEN_R    = 1.0      # Mover SL a BE cuando precio alcanza 1R
ORB_NEWS_BUFFER    = 60       # Minutos bloqueados por noticias (oro es más sensible)

# ─────────────────────────────────────────────
# EJECUCIÓN MT5
# ─────────────────────────────────────────────
MT5_MAGIC_NUMBER   = 234000   # ID único de nuestras operaciones
MT5_DEVIATION_PIPS = 10       # Slippage máximo permitido
MT5_MAX_LOT        = 10.0     # Lote máximo por operación

# ─────────────────────────────────────────────
# LOOPS Y TEMPORIZACIÓN
# ─────────────────────────────────────────────
MAIN_LOOP_SLEEP_SEC     = 30   # Pausa entre iteraciones del bucle principal
HTF_UPDATE_INTERVAL_M5  = 12   # Actualizar HTF cada 12 velas M5 (= 1 hora)
BLOCK_WAIT_LONG_SEC     = 300  # Espera si bloqueado por reglas largas (weekend, xmas)
BLOCK_WAIT_SHORT_SEC    = 60   # Espera si bloqueado por reglas cortas (noticias)

# ─────────────────────────────────────────────
# FILTROS TEMPORALES
# ─────────────────────────────────────────────
XMAS_BLOCK_START = (12, 20)   # (mes, día) inicio bloqueo navideño
XMAS_BLOCK_END   = (1, 3)     # (mes, día) fin bloqueo navideño
FRIDAY_CLOSE_HOUR = 21        # Cierre el viernes a las 21:00 UTC
