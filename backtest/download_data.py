# import os
# from datetime import datetime, timedelta

# import MetaTrader5 as mt5
# import pandas as pd


# def save_rates_to_csv(rates, path: str):
#     if rates is None or len(rates) == 0:
#         print(f"  Sin datos -> {path}")
#         return

#     df = pd.DataFrame(rates)
#     df["time"] = pd.to_datetime(df["time"], unit="s")
#     df = df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
#     df.columns = ["open", "high", "low", "close", "vol"]

#     df = df.sort_index()
#     df = df[~df.index.duplicated(keep="last")]

#     os.makedirs("backtest/data", exist_ok=True)
#     df.to_csv(path)

#     print(
#         f"  Guardado: {path} | {len(df)} velas | "
#         f"Desde: {df.index[0]} Hasta: {df.index[-1]}"
#     )


# def download_mt5_range(symbol: str, timeframe_str: str, years: int):
#     tf_map = {
#         "1M":  mt5.TIMEFRAME_M1,
#         "5M":  mt5.TIMEFRAME_M5,
#         "15M": mt5.TIMEFRAME_M15,
#         "30M": mt5.TIMEFRAME_M30,
#         "1H":  mt5.TIMEFRAME_H1,
#         "4H":  mt5.TIMEFRAME_H4,
#         "1D":  mt5.TIMEFRAME_D1,
#     }

#     tf = tf_map[timeframe_str]
#     date_to = datetime.now()
#     date_from = date_to - timedelta(days=365 * years)

#     rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
#     print(f"  last_error {symbol} {timeframe_str}: {mt5.last_error()}")

#     path = f"backtest/data/{symbol}_{timeframe_str}.csv"
#     save_rates_to_csv(rates, path)


# def download_mt5_chunked(symbol: str, timeframe_str: str, years: int, chunk_days: int = 30):
#     tf_map = {
#         "1M": mt5.TIMEFRAME_M1,
#         "5M": mt5.TIMEFRAME_M5,
#     }

#     tf = tf_map[timeframe_str]
#     date_to = datetime.now()
#     date_from = date_to - timedelta(days=365 * years)

#     current_from = date_from
#     dfs = []

#     print(f"\nDescargando {symbol} {timeframe_str} por bloques de {chunk_days} días...")

#     while current_from < date_to:
#         current_to = min(current_from + timedelta(days=chunk_days), date_to)

#         rates = mt5.copy_rates_range(symbol, tf, current_from, current_to)
#         print(
#             f"  Bloque {current_from.strftime('%Y-%m-%d')} -> {current_to.strftime('%Y-%m-%d')} "
#             f"| last_error: {mt5.last_error()}"
#         )

#         if rates is not None and len(rates) > 0:
#             df = pd.DataFrame(rates)
#             df["time"] = pd.to_datetime(df["time"], unit="s")
#             df = df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
#             df.columns = ["open", "high", "low", "close", "vol"]
#             dfs.append(df)

#         current_from = current_to

#     if not dfs:
#         print(f"  Sin datos {timeframe_str} para {symbol}")
#         return

#     df_all = pd.concat(dfs)
#     df_all = df_all.sort_index()
#     df_all = df_all[~df_all.index.duplicated(keep="last")]

#     path = f"backtest/data/{symbol}_{timeframe_str}.csv"
#     os.makedirs("backtest/data", exist_ok=True)
#     df_all.to_csv(path)

#     print(
#         f"\n  Guardado final: {path} | {len(df_all)} velas | "
#         f"Desde: {df_all.index[0]} Hasta: {df_all.index[-1]}"
#     )


# if __name__ == "__main__":
#     if not mt5.initialize():
#         print("Error al inicializar MT5:", mt5.last_error())
#         raise SystemExit

#     symbol = "XAUUSD"

#     # Años de historial por timeframe
#     # (ajusta según lo que tu broker tenga disponible)
#     RANGES = {
#         "1M":  2,   # M1  → brokers raramente guardan más de 2-3 años
#         "5M":  3,   # M5  → suele haber hasta 3-5 años
#         "15M": 5,   # M15 → hasta 5 años
#         "30M": 5,   # M30 → hasta 5 años
#         "1H":  10,  # H1  → hasta 10 años
#         "4H":  15,  # H4  → hasta 15 años
#         "1D":  20,  # D1  → hasta 20+ años
#     }

#     print(f"\n{'='*40}")
#     print(f"Descargando {symbol}")
#     print(f"{'='*40}")

#     # M1 y M5 en bloques para evitar timeouts
#     download_mt5_chunked(symbol, "1M", years=RANGES["1M"], chunk_days=30)
#     download_mt5_chunked(symbol, "5M", years=RANGES["5M"], chunk_days=60)

#     # El resto de una sola llamada
#     for tf in ["15M", "30M", "1H", "4H", "1D"]:
#         print(f"\nDescargando {symbol} {tf} ({RANGES[tf]} años)...")
#         download_mt5_range(symbol, tf, years=RANGES[tf])

#     mt5.shutdown()
#     print("\n✅ Descarga completada.")
import os
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import pandas as pd


def save_rates_to_csv(rates, path: str):
    if rates is None or len(rates) == 0:
        print(f"  Sin datos -> {path}")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
    df.columns = ["open", "high", "low", "close", "vol"]

    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    os.makedirs("backtest/data", exist_ok=True)
    df.to_csv(path)

    print(
        f"  Guardado: {path} | {len(df)} velas | "
        f"Desde: {df.index[0]} Hasta: {df.index[-1]}"
    )


def download_mt5_range(symbol: str, timeframe_str: str, years: int):
    tf_map = {
        "1M":  mt5.TIMEFRAME_M1,
        "5M":  mt5.TIMEFRAME_M5,
        "15M": mt5.TIMEFRAME_M15,
        "30M": mt5.TIMEFRAME_M30,
        "1H":  mt5.TIMEFRAME_H1,
        "4H":  mt5.TIMEFRAME_H4,
        "1D":  mt5.TIMEFRAME_D1,
    }

    tf = tf_map[timeframe_str]
    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years)

    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)
    print(f"  last_error {symbol} {timeframe_str}: {mt5.last_error()}")

    path = f"backtest/data/{symbol}_{timeframe_str}.csv"
    save_rates_to_csv(rates, path)


def download_mt5_chunked(symbol: str, timeframe_str: str, years: int, chunk_days: int = 30):
    tf_map = {
        "1M": mt5.TIMEFRAME_M1,
        "5M": mt5.TIMEFRAME_M5,
    }

    tf = tf_map[timeframe_str]
    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years)

    current_from = date_from
    dfs = []

    print(f"\nDescargando {symbol} {timeframe_str} por bloques de {chunk_days} días...")

    while current_from < date_to:
        current_to = min(current_from + timedelta(days=chunk_days), date_to)

        rates = mt5.copy_rates_range(symbol, tf, current_from, current_to)
        print(
            f"  Bloque {current_from.strftime('%Y-%m-%d')} -> {current_to.strftime('%Y-%m-%d')} "
            f"| last_error: {mt5.last_error()}"
        )

        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
            df.columns = ["open", "high", "low", "close", "vol"]
            dfs.append(df)

        current_from = current_to

    if not dfs:
        print(f"  Sin datos {timeframe_str} para {symbol}")
        return

    df_all = pd.concat(dfs)
    df_all = df_all.sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]

    path = f"backtest/data/{symbol}_{timeframe_str}.csv"
    os.makedirs("backtest/data", exist_ok=True)
    df_all.to_csv(path)

    print(
        f"\n  Guardado final: {path} | {len(df_all)} velas | "
        f"Desde: {df_all.index[0]} Hasta: {df_all.index[-1]}"
    )


if __name__ == "__main__":
    if not mt5.initialize():
        print("Error al inicializar MT5:", mt5.last_error())
        raise SystemExit

    symbol = "XAUUSD"

    # Años de historial por timeframe
    # (ajusta según lo que tu broker tenga disponible)
    RANGES = {
        "1M":  2,   # M1  → brokers raramente guardan más de 2-3 años
        "5M":  3,   # M5  → suele haber hasta 3-5 años
        "15M": 5,   # M15 → hasta 5 años
        "30M": 5,   # M30 → hasta 5 años
        "1H":  10,  # H1  → hasta 10 años
        "4H":  15,  # H4  → hasta 15 años
        "1D":  20,  # D1  → hasta 20+ años
    }

    print(f"\n{'='*40}")
    print(f"Descargando {symbol}")
    print(f"{'='*40}")

    # M1 y M5 en bloques para evitar timeouts
    download_mt5_chunked(symbol, "1M", years=RANGES["1M"], chunk_days=30)
    download_mt5_chunked(symbol, "5M", years=RANGES["5M"], chunk_days=60)

    # El resto de una sola llamada
    for tf in ["15M", "30M", "1H", "4H", "1D"]:
        print(f"\nDescargando {symbol} {tf} ({RANGES[tf]} años)...")
        download_mt5_range(symbol, tf, years=RANGES[tf])

    mt5.shutdown()
    print("\n✅ Descarga completada.")
