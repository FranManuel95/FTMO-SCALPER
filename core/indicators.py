# core/indicators.py — Biblioteca central de indicadores técnicos
# Todos los backtesters y el motor de señales importan desde aquí.
# Evita duplicación y garantiza cálculos consistentes en toda la estrategia.

import pandas as pd
import numpy as np


# ─────────────────────────────────────────────
# MEDIAS MÓVILES
# ─────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (SMA)."""
    return series.rolling(period).mean()


# ─────────────────────────────────────────────
# VOLATILIDAD
# ─────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range. Requiere columnas: high, low, close."""
    hl  = df['high'] - df['low']
    hcp = (df['high'] - df['close'].shift()).abs()
    lcp = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range sin suavizar."""
    hl  = df['high'] - df['low']
    hcp = (df['high'] - df['close'].shift()).abs()
    lcp = (df['low']  - df['close'].shift()).abs()
    return pd.concat([hl, hcp, lcp], axis=1).max(axis=1)


# ─────────────────────────────────────────────
# MOMENTUM
# ─────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI con Wilder's smoothing — consistente con TradingView y MT5."""
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


# ─────────────────────────────────────────────
# TENDENCIA
# ─────────────────────────────────────────────

def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    ADX con +DI y -DI. Requiere columnas: high, low, close.
    Devuelve DataFrame con columnas: adx, plus_di, minus_di.
    """
    up_move   = df['high'].diff()
    down_move = -df['low'].diff()

    plus_dm  = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr_smooth  = true_range(df).ewm(alpha=1/period, adjust=False).mean()
    plus_di    = 100 * plus_dm.ewm(alpha=1/period, adjust=False).mean() / (tr_smooth + 1e-10)
    minus_di   = 100 * minus_dm.ewm(alpha=1/period, adjust=False).mean() / (tr_smooth + 1e-10)
    dx         = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx_val    = dx.ewm(alpha=1/period, adjust=False).mean()

    return pd.DataFrame({
        'adx':      adx_val,
        'plus_di':  plus_di,
        'minus_di': minus_di,
    }, index=df.index)


# ─────────────────────────────────────────────
# VWAP
# ─────────────────────────────────────────────

def vwap_ema(series: pd.Series, span: int = 20) -> pd.Series:
    """VWAP aproximado con EMA — proxy válido en M5/M15 sin volumen real."""
    return series.ewm(span=span, adjust=False).mean()


def vwap_real(df: pd.DataFrame) -> pd.Series:
    """VWAP real si hay columna tick_volume o volume. Si no, usa vwap_ema."""
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else \
              'volume'       if 'volume'      in df.columns else None
    if vol_col is None:
        return vwap_ema(df['close'])
    typical    = (df['high'] + df['low'] + df['close']) / 3
    vol        = df[vol_col]
    return (typical * vol).cumsum() / (vol.cumsum() + 1e-10)


# ─────────────────────────────────────────────
# CANDLE HELPERS
# ─────────────────────────────────────────────

def body_ratio(df: pd.DataFrame) -> pd.Series:
    """Ratio cuerpo/rango total de la vela (0-1)."""
    body  = (df['close'] - df['open']).abs()
    total = (df['high'] - df['low']).replace(0, np.nan)
    return body / total


# ─────────────────────────────────────────────
# HELPER PARA BACKTESTS
# ─────────────────────────────────────────────

def add_indicators_mtf(df: pd.DataFrame,
                       ema_fast: int = 20,
                       ema_slow: int = 50,
                       ema_trend: int = 200,
                       adx_period: int = 14,
                       rsi_period: int = 14,
                       atr_period: int = 14) -> pd.DataFrame:
    """Añade todos los indicadores MTF de una vez. Útil en backtests."""
    df = df.copy()
    df['ema_fast']  = ema(df['close'], ema_fast)
    df['ema_slow']  = ema(df['close'], ema_slow)
    df['ema_trend'] = ema(df['close'], ema_trend)
    df['atr']       = atr(df, atr_period)
    df['rsi']       = rsi(df['close'], rsi_period)
    df['vwap']      = vwap_ema(df['close'])

    adx_df = adx(df, adx_period)
    df['adx']      = adx_df['adx']
    df['plus_di']  = adx_df['plus_di']
    df['minus_di'] = adx_df['minus_di']

    return df.dropna()
