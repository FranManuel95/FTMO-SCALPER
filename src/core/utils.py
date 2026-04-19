from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def save_yaml(data: dict, path: str | Path) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def flatten_dict(d: dict, sep: str = ".") -> dict:
    result: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            for sub_key, sub_val in flatten_dict(value, sep).items():
                result[f"{key}{sep}{sub_key}"] = sub_val
        else:
            result[key] = value
    return result


def pips_to_price(pips: float, symbol: str) -> float:
    jpy_pairs = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"]
    if any(s in symbol.upper() for s in jpy_pairs):
        return pips * 0.01
    return pips * 0.0001


def resample_ohlcv(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(timeframe).agg(agg).dropna()
