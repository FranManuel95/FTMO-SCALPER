import numpy as np
import pandas as pd

try:
    import talib as _talib
    _USE_TALIB = True
except ImportError:
    _USE_TALIB = False
    from ta.trend import ADXIndicator, EMAIndicator


def add_htf_trend(
    df: pd.DataFrame,
    htf_resample: str = "4h",
    ema_fast: int = 50,
    ema_slow: int = 200,
) -> pd.DataFrame:
    """
    Calcula la tendencia en un timeframe superior resampleando el DataFrame base.
    Añade columnas: htf_ema_fast, htf_ema_slow, htf_trend (1=alcista, -1=bajista, 0=neutro)

    No requiere cargar un CSV separado: resamplea el 15m directamente a H4.
    """
    ohlcv = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    htf = df.resample(htf_resample).agg(ohlcv).dropna(subset=["close"])

    if _USE_TALIB:
        htf[f"htf_ema_{ema_fast}"] = _talib.EMA(htf["close"].values, timeperiod=ema_fast)
        htf[f"htf_ema_{ema_slow}"] = _talib.EMA(htf["close"].values, timeperiod=ema_slow)
    else:
        htf[f"htf_ema_{ema_fast}"] = EMAIndicator(htf["close"], window=ema_fast, fillna=False).ema_indicator()
        htf[f"htf_ema_{ema_slow}"] = EMAIndicator(htf["close"], window=ema_slow, fillna=False).ema_indicator()

    def _trend(row):
        f = row[f"htf_ema_{ema_fast}"]
        s = row[f"htf_ema_{ema_slow}"]
        if pd.isna(f) or pd.isna(s):
            return 0
        if row["close"] > f > s:
            return 1   # alcista
        if row["close"] < f < s:
            return -1  # bajista
        return 0       # neutro / indefinido

    htf["htf_trend"] = htf.apply(_trend, axis=1)

    # Merge al timeframe original: forward fill (la tendencia H4 no cambia hasta la siguiente vela H4)
    trend_cols = [f"htf_ema_{ema_fast}", f"htf_ema_{ema_slow}", "htf_trend"]
    df = df.join(htf[trend_cols], how="left").ffill()

    return df


def add_htf_adx(
    df: pd.DataFrame,
    htf_resample: str = "1D",
    adx_length: int = 14,
) -> pd.DataFrame:
    """
    Calcula el ADX en un timeframe superior (por defecto Daily).
    Añade columna: htf_adx_{length} — permite filtrar regímenes laterales.
    Solo operar cuando htf_adx > umbral (ej: 20) garantiza que el mercado esté tendencial.
    """
    ohlcv = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    htf = df.resample(htf_resample).agg(ohlcv).dropna(subset=["close"])

    col = f"htf_adx_{adx_length}"
    if _USE_TALIB:
        htf[col] = _talib.ADX(htf["high"].values, htf["low"].values, htf["close"].values, timeperiod=adx_length)
    else:
        adx = ADXIndicator(htf["high"], htf["low"], htf["close"], window=adx_length, fillna=False)
        htf[col] = adx.adx()

    df = df.join(htf[[col]], how="left").ffill()
    return df
