import pandas as pd
import pandas_ta as ta


def add_adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    adx = ta.adx(df["high"], df["low"], df["close"], length=length)
    df[f"adx_{length}"] = adx[f"ADX_{length}"]
    df[f"dmp_{length}"] = adx[f"DMP_{length}"]
    df[f"dmn_{length}"] = adx[f"DMN_{length}"]
    return df


def add_atr(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df[f"atr_{length}"] = ta.atr(df["high"], df["low"], df["close"], length=length)
    return df


def add_ema(df: pd.DataFrame, lengths: list[int] = [20, 50, 200]) -> pd.DataFrame:
    for length in lengths:
        df[f"ema_{length}"] = ta.ema(df["close"], length=length)
    return df


def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    df[f"rsi_{length}"] = ta.rsi(df["close"], length=length)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    df["macd"] = macd[f"MACD_{fast}_{slow}_{signal}"]
    df["macd_signal"] = macd[f"MACDs_{fast}_{slow}_{signal}"]
    df["macd_hist"] = macd[f"MACDh_{fast}_{slow}_{signal}"]
    return df


def add_bollinger(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    bb = ta.bbands(df["close"], length=length, std=std)
    df["bb_upper"] = bb[f"BBU_{length}_{std}"]
    df["bb_mid"] = bb[f"BBM_{length}_{std}"]
    df["bb_lower"] = bb[f"BBL_{length}_{std}"]
    df["bb_width"] = bb[f"BBB_{length}_{std}"]
    return df


def add_all_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = add_atr(df, 14)
    df = add_adx(df, 14)
    df = add_ema(df, [20, 50, 200])
    df = add_rsi(df, 14)
    return df
