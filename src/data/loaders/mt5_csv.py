from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.loaders.base import BaseLoader

# Mapeo desde los args del backtest (15m, 1h) a los sufijos de archivo MT5
TIMEFRAME_SUFFIXES = {
    "1m":  ["1M", "M1"],
    "5m":  ["5M", "M5"],
    "15m": ["15M", "M15"],
    "30m": ["30M", "M30"],
    "1h":  ["1H", "H1"],
    "4h":  ["4H", "H4"],
    "1d":  ["1D", "D1"],
}

# Directorios donde buscar CSVs (en orden de prioridad)
SEARCH_DIRS = [
    Path("data/raw"),
    Path("data"),
    Path("backtest/data"),
]


def find_csv(symbol: str, timeframe: str) -> Path | None:
    """Busca el CSV de MT5 probando varios nombres y directorios."""
    suffixes = TIMEFRAME_SUFFIXES.get(timeframe.lower(), [timeframe.upper()])
    symbol = symbol.upper()

    for directory in SEARCH_DIRS:
        for suffix in suffixes:
            candidates = [
                directory / f"{symbol}_{suffix}.csv",
                directory / f"{symbol.lower()}_{suffix.lower()}.csv",
                directory / f"{symbol}_{suffix.lower()}.csv",
            ]
            for path in candidates:
                if path.exists():
                    return path
    return None


def _parse_mt5_csv(path: Path) -> pd.DataFrame:
    """
    Parsea CSVs exportados desde MetaTrader 5.
    Soporta los dos formatos comunes:
    - Tab-sep: <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>...
    - Comma-sep: DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICK_VOLUME,...
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        first_line = f.readline().strip()

    sep = "\t" if "\t" in first_line else ","

    df = pd.read_csv(path, sep=sep, encoding="utf-8", encoding_errors="replace")

    # Normalizar nombres de columnas: quitar <>, bajar a minúsculas
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]

    # Renombres comunes de MT5
    rename_map = {
        "tickvol": "volume",
        "tick_volume": "volume",
        "vol": "volume",
        "real_volume": "volume",
        "spread": "spread",
    }
    df.rename(columns=rename_map, inplace=True)

    # Construir índice datetime — soporta varias convenciones de MT5
    if "date" in df.columns and "time" in df.columns:
        df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"], utc=True)
    elif "date" in df.columns:
        df["datetime"] = pd.to_datetime(df["date"], utc=True)
    elif "time" in df.columns:
        # Formato simple: columna 'time' contiene datetime completo (ej. "2022-01-14 15:30:00")
        df["datetime"] = pd.to_datetime(df["time"], utc=True)
    else:
        cols = list(df.columns)
        raise ValueError(f"No se encontró columna de fecha en {path.name}. Columnas: {cols}")

    df.set_index("datetime", inplace=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "datetime"

    # Asegurar columnas OHLCV numéricas
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    return df[["open", "high", "low", "close", "volume"]].dropna(
        subset=["open", "high", "low", "close"]
    )


class MT5CsvLoader(BaseLoader):
    """Carga datos históricos exportados desde MetaTrader 5 en formato CSV."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir:
            SEARCH_DIRS.insert(0, Path(data_dir))

    def load(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "15m",
    ) -> pd.DataFrame:
        path = find_csv(symbol, timeframe)
        if path is None:
            searched = [str(d) for d in SEARCH_DIRS]
            raise FileNotFoundError(
                f"No se encontró CSV para {symbol} {timeframe}. "
                f"Directorios buscados: {searched}. "
                f"Nombres esperados: {symbol}_{{{','.join(TIMEFRAME_SUFFIXES.get(timeframe, [timeframe]))}}}.csv"
            )

        df = _parse_mt5_csv(path)

        # Filtrar por rango de fechas — start/end pueden llegar ya tz-aware
        start_ts = pd.Timestamp(start).tz_localize("UTC") if pd.Timestamp(start).tzinfo is None else pd.Timestamp(start).tz_convert("UTC")
        end_ts = pd.Timestamp(end).tz_localize("UTC") if pd.Timestamp(end).tzinfo is None else pd.Timestamp(end).tz_convert("UTC")
        df = df[(df.index >= start_ts) & (df.index < end_ts)]

        return self.validate(df)
