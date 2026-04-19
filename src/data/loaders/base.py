from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class BaseLoader(ABC):
    """Interfaz base para todos los loaders de datos de mercado."""

    @abstractmethod
    def load(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
    ) -> pd.DataFrame:
        """
        Retorna OHLCV con índice datetime UTC.
        Columnas esperadas: open, high, low, close, volume
        """
        ...

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Columnas faltantes: {missing}")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("El índice debe ser DatetimeIndex")
        return df.dropna(subset=list(required))
