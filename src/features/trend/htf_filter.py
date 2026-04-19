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


def add_daily_trend(
    df: pd.DataFrame,
    ema_fast: int = 50,
    ema_slow: int = 200,
) -> pd.DataFrame:
    """
    Filtro de régimen diario: EMA50 vs EMA200 en Daily (golden/death cross).
    Añade columna 'daily_trend': 1=alcista (EMA50 > EMA200), -1=bajista, 0=indefinido.

    La señal se desplaza un día (shift=1) para evitar look-ahead: usamos el cierre
    del día anterior para decidir si operamos hoy.
    Warmup: ~200 velas diarias ≈ 10 meses. Con datos desde Jan-2022, válido desde ~Oct-2022.
    """
    ohlcv = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    daily = df.resample("1D").agg(ohlcv).dropna(subset=["close"])

    if _USE_TALIB:
        daily["d_ema_fast"] = _talib.EMA(daily["close"].values, timeperiod=ema_fast)
        daily["d_ema_slow"] = _talib.EMA(daily["close"].values, timeperiod=ema_slow)
    else:
        daily["d_ema_fast"] = EMAIndicator(daily["close"], window=ema_fast, fillna=False).ema_indicator()
        daily["d_ema_slow"] = EMAIndicator(daily["close"], window=ema_slow, fillna=False).ema_indicator()

    valid = daily["d_ema_fast"].notna() & daily["d_ema_slow"].notna()
    daily["daily_trend"] = 0
    daily.loc[valid & (daily["d_ema_fast"] > daily["d_ema_slow"]), "daily_trend"] = 1
    daily.loc[valid & (daily["d_ema_fast"] < daily["d_ema_slow"]), "daily_trend"] = -1

    # Shift: usar cierre de ayer para hoy (evita look-ahead intradiario)
    daily["daily_trend"] = daily["daily_trend"].shift(1).fillna(0).astype(int)

    df = df.join(daily[["daily_trend"]], how="left").ffill().fillna(0)
    df["daily_trend"] = df["daily_trend"].astype(int)
    return df


def add_weekly_regime(
    df: pd.DataFrame,
    ema_period: int = 50,
) -> pd.DataFrame:
    """
    Filtro de régimen macro: close semanal vs EMA50 semanal.
    Añade columna 'weekly_regime': 1=alcista (close > EMA50 weekly), -1=bajista, 0=neutral.

    Permite bloquear trades en contra del macro trend — p.ej. no abrir longs
    en XAUUSD cuando el precio está por debajo de la EMA50 semanal.
    """
    ohlcv = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    weekly = df.resample("1W").agg(ohlcv).dropna(subset=["close"])

    col = f"weekly_ema_{ema_period}"
    if _USE_TALIB:
        weekly[col] = _talib.EMA(weekly["close"].values, timeperiod=ema_period)
    else:
        weekly[col] = EMAIndicator(weekly["close"], window=ema_period, fillna=False).ema_indicator()

    def _regime(row):
        ema = row[col]
        if pd.isna(ema):
            return 0
        return 1 if row["close"] > ema else -1

    weekly["weekly_regime"] = weekly.apply(_regime, axis=1)

    df = df.join(weekly[["weekly_regime"]], how="left").ffill()
    return df
