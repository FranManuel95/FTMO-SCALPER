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
SYMBOLS_MTF      = ["EURUSD", "GBPUSD"]
SYMBOLS_BREAKOUT = ["USDJPY", "EURJPY"]
SYMBOLS_ORB      = ["XAUUSD"]
ALL_SYMBOLS      = SYMBOLS_MTF + SYMBOLS_BREAKOUT + SYMBOLS_ORB

# ─────────────────────────────────────────────
# SESIONES DE MERCADO (UTC)
# ─────────────────────────────────────────────
LONDON_OPEN   = (7, 0)
LONDON_CLOSE  = (17, 0)
NY_OPEN       = (13, 0)
NY_CLOSE      = (20, 0)
ASIAN_OPEN    = (0, 0)
ASIAN_CLOSE   = (7, 0)

# ─────────────────────────────────────────────
# INDICADORES — ESTRATEGIA MTF (EURUSD/GBPUSD)
# ─────────────────────────────────────────────
MTF_EMA_TREND   = 200
MTF_EMA_FAST    = 20
MTF_EMA_SLOW    = 50
MTF_EMA_ENTRY   = 9
MTF_EMA_CONFIRM = 21
MTF_ADX_PERIOD  = 14
MTF_ADX_MIN     = 18
MTF_ADX_MAX     = 58
MTF_RSI_PERIOD  = 14
MTF_ATR_PERIOD  = 14
MTF_ATR_SL_MULT = 1.2
MTF_RR_RATIO    = 1.6
MTF_ATR_MIN     = 0.0003
MTF_TRAIL_MULT  = 2.0

# ─────────────────────────────────────────────
# INDICADORES — BREAKOUT (USDJPY/EURJPY)
# ─────────────────────────────────────────────
BRK_ATR_PERIOD      = 14
BRK_ATR_SL_MULT     = 1.5
BRK_RR_RATIO        = 2.0
BRK_BUFFER_PIPS     = 0.04
BRK_MIN_BODY_RATIO  = 0.50
BRK_MAX_HOLD_BARS   = 42

# ─────────────────────────────────────────────
# INDICADORES — ORB (XAUUSD)
# ─────────────────────────────────────────────
ORB_WINDOW_OPEN    = (7, 0)
ORB_WINDOW_CLOSE   = (9, 0)
ORB_TRADE_OPEN     = (9, 0)
ORB_TRADE_CLOSE    = (16, 0)
ORB_ATR_PERIOD     = 14
ORB_ATR_SL_MULT    = 1.2
ORB_RR_RATIO       = 2.0
ORB_BREAKEVEN_R    = 1.0
ORB_NEWS_BUFFER    = 60

# ─────────────────────────────────────────────
# EJECUCIÓN MT5
# ─────────────────────────────────────────────
MT5_MAGIC_NUMBER   = 234000
MT5_DEVIATION_PIPS = 10
MT5_MAX_LOT        = 10.0

# ─────────────────────────────────────────────
# LOOPS Y TEMPORIZACIÓN
# ─────────────────────────────────────────────
MAIN_LOOP_SLEEP_SEC     = 30
HTF_UPDATE_INTERVAL_M5  = 12
BLOCK_WAIT_LONG_SEC     = 300
BLOCK_WAIT_SHORT_SEC    = 60

# ─────────────────────────────────────────────
# FILTROS TEMPORALES
# ─────────────────────────────────────────────
XMAS_BLOCK_START  = (12, 20)
XMAS_BLOCK_END    = (1, 3)
FRIDAY_CLOSE_HOUR = 21

