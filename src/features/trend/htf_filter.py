import pandas as pd
from ta.trend import EMAIndicator


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
