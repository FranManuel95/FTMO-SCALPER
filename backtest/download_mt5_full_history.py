import os
from datetime import datetime, timedelta
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd


TF_MAP = {
    "1M": mt5.TIMEFRAME_M1,
    "5M": mt5.TIMEFRAME_M5,
    "15M": mt5.TIMEFRAME_M15,
    "30M": mt5.TIMEFRAME_M30,
    "1H": mt5.TIMEFRAME_H1,
    "4H": mt5.TIMEFRAME_H4,
    "1D": mt5.TIMEFRAME_D1,
}

# Rangos objetivo. Si el broker da menos, se guarda lo que haya.
DEFAULT_RANGES = {
    "1M": 2,
    "5M": 4,
    "15M": 5,
    "30M": 5,
    "1H": 8,
    "4H": 12,
    "1D": 20,
}

# Bloques para evitar problemas en timeframes pequeños
CHUNK_DAYS = {
    "1M": 30,
    "5M": 60,
}


def resolve_symbol(base_symbol: str) -> Optional[str]:
    """
    Intenta encontrar el símbolo real en MT5 aunque el broker use sufijos/prefijos.
    Prioridad:
    1) exacto
    2) empieza por base_symbol
    3) contiene base_symbol
    """
    symbols = mt5.symbols_get()
    if not symbols:
        return None

    names = [s.name for s in symbols]

    if base_symbol in names:
        return base_symbol

    starts = [n for n in names if n.startswith(base_symbol)]
    if starts:
        return starts[0]

    contains = [n for n in names if base_symbol in n]
    if contains:
        return contains[0]

    return None


def ensure_symbol_selected(symbol: str) -> bool:
    info = mt5.symbol_info(symbol)
    if info is None:
        return False

    if info.visible:
        return True

    return mt5.symbol_select(symbol, True)


def rates_to_df(rates) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
    df.columns = ["open", "high", "low", "close", "vol"]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def save_df(df: pd.DataFrame, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path)
    print(
        f"  Guardado: {path} | {len(df)} velas | "
        f"Desde: {df.index[0]} Hasta: {df.index[-1]}"
    )


def validate_symbol_price(real_symbol: str):
    info = mt5.symbol_info(real_symbol)
    tick = mt5.symbol_info_tick(real_symbol)

    print(f"  Símbolo real MT5: {real_symbol}")
    if info is not None:
        print(
            f"  digits={info.digits} | point={info.point} | visible={info.visible}"
        )

    if tick is not None:
        print(f"  bid={tick.bid} | ask={tick.ask} | last={tick.last}")
    else:
        print("  No hay tick disponible ahora mismo.")


def download_range_once(real_symbol: str, timeframe_str: str, years: int) -> Optional[pd.DataFrame]:
    tf = TF_MAP[timeframe_str]
    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years)

    rates = mt5.copy_rates_range(real_symbol, tf, date_from, date_to)
    print(f"  last_error {real_symbol} {timeframe_str}: {mt5.last_error()}")

    if rates is None or len(rates) == 0:
        return None

    return rates_to_df(rates)


def download_range_chunked(
    real_symbol: str,
    timeframe_str: str,
    years: int,
    chunk_days: int,
) -> Optional[pd.DataFrame]:
    tf = TF_MAP[timeframe_str]
    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years)

    current_from = date_from
    dfs = []

    print(f"  Descargando por bloques de {chunk_days} días...")

    while current_from < date_to:
        current_to = min(current_from + timedelta(days=chunk_days), date_to)
        rates = mt5.copy_rates_range(real_symbol, tf, current_from, current_to)

        print(
            f"    Bloque {current_from.strftime('%Y-%m-%d')} -> {current_to.strftime('%Y-%m-%d')} "
            f"| barras: {0 if rates is None else len(rates)} "
            f"| last_error: {mt5.last_error()}"
        )

        if rates is not None and len(rates) > 0:
            dfs.append(rates_to_df(rates))

        current_from = current_to

    if not dfs:
        return None

    df_all = pd.concat(dfs)
    df_all = df_all.sort_index()
    df_all = df_all[~df_all.index.duplicated(keep="last")]
    return df_all


def download_symbol_timeframe(base_symbol: str, timeframe_str: str, years: int):
    if timeframe_str not in TF_MAP:
        print(f"  Timeframe no soportado: {timeframe_str}")
        return

    real_symbol = resolve_symbol(base_symbol)
    if not real_symbol:
        print(f"  No encontré símbolo MT5 para: {base_symbol}")
        return

    if not ensure_symbol_selected(real_symbol):
        print(f"  No pude activar el símbolo: {real_symbol}")
        return

    print(f"\nDescargando {base_symbol} {timeframe_str}")
    validate_symbol_price(real_symbol)

    if timeframe_str in CHUNK_DAYS:
        df = download_range_chunked(
            real_symbol=real_symbol,
            timeframe_str=timeframe_str,
            years=years,
            chunk_days=CHUNK_DAYS[timeframe_str],
        )
    else:
        df = download_range_once(
            real_symbol=real_symbol,
            timeframe_str=timeframe_str,
            years=years,
        )

    if df is None or df.empty:
        print(f"  Sin datos para {base_symbol} {timeframe_str}")
        return

    out_path = f"backtest/data/{base_symbol}_{timeframe_str}.csv"
    save_df(df, out_path)

    print("\n  Primeras 3 filas:")
    print(df[["open", "high", "low", "close"]].head(3).to_string())

    print("\n  Últimas 3 filas:")
    print(df[["open", "high", "low", "close"]].tail(3).to_string())


def download_symbol_all_timeframes(base_symbol: str, ranges: dict[str, int]):
    print(f"\n{'=' * 50}")
    print(f"Descargando {base_symbol}")
    print(f"{'=' * 50}")

    for tf in ["1M", "5M", "15M", "30M", "1H", "4H", "1D"]:
        years = ranges.get(tf)
        if years is None:
            continue
        download_symbol_timeframe(base_symbol, tf, years=years)


if __name__ == "__main__":
    if not mt5.initialize():
        print("Error al inicializar MT5:", mt5.last_error())
        raise SystemExit

    # Cambia aquí los símbolos que quieras descargar
    symbols = [
        "EURJPY",
        "GBPJPY",
        "GBPUSD",
        "XAUUSD",
        "EURUSD",
        "AUDUSD",
        "USDCAD",
        "NZDUSD",
        "USDCHF"
    ]

    for symbol in symbols:
        download_symbol_all_timeframes(symbol, DEFAULT_RANGES)

    mt5.shutdown()
    print("\n✅ Descarga completada.")