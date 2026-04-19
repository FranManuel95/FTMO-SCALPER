import numpy as np
import pandas as pd
import talib


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df[f"atr_{length}"] = talib.ATR(df["high"].values, df["low"].values, df["close"].values, timeperiod=length)
    return df


def add_adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df[f"adx_{length}"] = talib.ADX(df["high"].values, df["low"].values, df["close"].values, timeperiod=length)
    df[f"dmp_{length}"] = talib.PLUS_DI(df["high"].values, df["low"].values, df["close"].values, timeperiod=length)
    df[f"dmn_{length}"] = talib.MINUS_DI(df["high"].values, df["low"].values, df["close"].values, timeperiod=length)
    return df


def add_ema(df: pd.DataFrame, lengths: list[int] = [20, 50, 200]) -> pd.DataFrame:
    for length in lengths:
        df[f"ema_{length}"] = talib.EMA(df["close"].values, timeperiod=length)
    return df


def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df[f"rsi_{length}"] = talib.RSI(df["close"].values, timeperiod=length)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd, macd_signal, macd_hist = talib.MACD(df["close"].values, fastperiod=fast, slowperiod=slow, signalperiod=signal)
    df["macd"] = macd
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist
    return df


def add_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    upper, mid, lower = talib.BBANDS(df["close"].values, timeperiod=length, nbdevup=std, nbdevdn=std)
    df["bb_upper"] = upper
    df["bb_mid"] = mid
    df["bb_lower"] = lower
    df["bb_width"] = (upper - lower) / mid
    return df


def add_all_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_atr(df, 14)
    df = add_adx(df, 14)
    df = add_ema(df, [20, 50, 200])
    df = add_rsi(df, 14)
    return df
