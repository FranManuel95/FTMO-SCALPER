import pandas as pd
import os

def resample_from_5m(symbol: str, timeframes: list):
    path_5m = f"backtest/data/{symbol}_5M.csv"
    df = pd.read_csv(path_5m, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_index()
    print(f"{symbol} 5M cargado: {len(df)} velas")

    tf_map = {
        '30M': '30min',
        '4H':  '4h',
        '1H':  '1h',
    }

    for tf_name, rule in tf_map.items():
        if tf_name not in timeframes:
            continue
        resampled = df.resample(rule).agg({
            'open':  'first',
            'high':  'max',
            'low':   'min',
            'close': 'last'
        }).dropna()
        path_out = f"backtest/data/{symbol}_{tf_name}.csv"
        resampled.to_csv(path_out)
        print(f"  {tf_name}: {len(resampled)} velas → {path_out}")

if __name__ == "__main__":
    resample_from_5m("XAUUSD", ["30M", "4H"])
    resample_from_5m("USDJPY", ["30M", "4H"])