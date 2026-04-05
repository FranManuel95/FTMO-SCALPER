# backtest/download_data.py — Descarga multi-timeframe desde Dukascopy

import requests
import struct
import lzma
import pandas as pd
import os
from datetime import datetime, timedelta

def download_dukascopy_hour(symbol: str, dt: datetime) -> pd.DataFrame:
    url = (f"https://datafeed.dukascopy.com/datafeed/{symbol}/"
           f"{dt.year}/{dt.month-1:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5")
    try:
        resp = requests.get(url, timeout=15,
                           headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or len(resp.content) == 0:
            return pd.DataFrame()
        data = lzma.decompress(resp.content)
        ticks = []
        for i in range(0, len(data), 20):
            chunk = data[i:i+20]
            if len(chunk) < 20: break
            ms, ask, bid, ask_vol, bid_vol = struct.unpack('>IIIff', chunk)
            timestamp = dt + timedelta(milliseconds=ms)
            price = bid / 100000.0
            ticks.append({'time': timestamp, 'price': price})
        if not ticks:
            return pd.DataFrame()
        df = pd.DataFrame(ticks).set_index('time')
        return df
    except Exception:
        return pd.DataFrame()

def download_month_timeframe(symbol: str, year: int,
                              month: int, timeframe: str) -> pd.DataFrame:
    print(f"  Descargando {symbol} {timeframe} {year}/{month:02d}...")
    frames = []
    start = datetime(year, month, 1)
    end   = datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)

    current = start
    while current < end:
        for hour in range(24):
            dt = datetime(current.year, current.month, current.day, hour)
            df = download_dukascopy_hour(symbol, dt)
            if not df.empty:
                frames.append(df)
        current += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    # Concatenar todos los ticks
    all_ticks = pd.concat(frames).sort_index()
    all_ticks = all_ticks[~all_ticks.index.duplicated()]

    # Resamplear al timeframe pedido
    tf_map = {'5m': '5min', '15m': '15min', '1h': '1h'}
    rule = tf_map.get(timeframe, '5min')

    df_resampled = all_ticks['price'].resample(rule).ohlc().dropna()
    print(f"    OK - {len(df_resampled)} velas {timeframe}")
    return df_resampled

def download_all_timeframes(symbol: str = "EURUSD", months: int = 6):
    end_date   = datetime.utcnow()
    start_date = end_date - timedelta(days=months * 30)

    for tf in ['5m', '15m', '1h']:
        frames = []
        current = datetime(start_date.year, start_date.month, 1)

        print(f"\nDescargando {tf}...")
        while current <= end_date:
            df = download_month_timeframe(symbol, current.year, current.month, tf)
            if not df.empty:
                frames.append(df)
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)

        if frames:
            full_df = pd.concat(frames).sort_index()
            full_df = full_df[~full_df.index.duplicated()]
            os.makedirs("backtest/data", exist_ok=True)
            path = f"backtest/data/{symbol}_{tf.upper()}.csv"
            full_df.to_csv(path)
            print(f"  Total: {len(full_df)} velas guardadas en {path}")

if __name__ == "__main__":
    download_all_timeframes("EURUSD", months=6)