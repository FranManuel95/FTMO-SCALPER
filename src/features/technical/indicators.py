import pandas as pd
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    atr = AverageTrueRange(df["high"], df["low"], df["close"], window=length, fillna=False)
    df[f"atr_{length}"] = atr.average_true_range()
    return df


def add_adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    adx = ADXIndicator(df["high"], df["low"], df["close"], window=length, fillna=False)
    df[f"adx_{length}"] = adx.adx()
    df[f"dmp_{length}"] = adx.adx_pos()
    df[f"dmn_{length}"] = adx.adx_neg()
    return df


def add_ema(df: pd.DataFrame, lengths: list[int] = [20, 50, 200]) -> pd.DataFrame:
    for length in lengths:
        ema = EMAIndicator(df["close"], window=length, fillna=False)
        df[f"ema_{length}"] = ema.ema_indicator()
    return df


def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    rsi = RSIIndicator(df["close"], window=length, fillna=False)
    df[f"rsi_{length}"] = rsi.rsi()
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd = MACD(df["close"], window_fast=fast, window_slow=slow, window_sign=signal, fillna=False)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    return df


def add_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    bb = BollingerBands(df["close"], window=length, window_dev=std, fillna=False)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_width"] = bb.bollinger_wband()
    return df


def add_all_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_atr(df, 14)
    df = add_adx(df, 14)
    df = add_ema(df, [20, 50, 200])
    df = add_rsi(df, 14)
    return df
