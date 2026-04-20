"""
LiveDataLoader — descarga barras en tiempo real desde MT5 como DataFrame.

El DataFrame devuelto es compatible al 100% con los signal generators existentes:
  - Index: DatetimeIndex UTC, nombre 'datetime'
  - Columnas: open, high, low, close, volume
  - attrs['symbol'] fijado al símbolo del instrumento

Esto permite reutilizar TODO el código de investigación sin cambios.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from .mt5_client import MT5Client

logger = logging.getLogger(__name__)


_TIMEFRAME_MAP = {
    "1m":  "TIMEFRAME_M1",
    "5m":  "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "30m": "TIMEFRAME_M30",
    "1h":  "TIMEFRAME_H1",
    "4h":  "TIMEFRAME_H4",
    "1d":  "TIMEFRAME_D1",
}


class LiveDataLoader:
    def __init__(self, client: MT5Client):
        self.client = client

    def get_bars(self, symbol: str, timeframe: str, n_bars: int = 500) -> pd.DataFrame:
        """
        Descarga las últimas n_bars barras del símbolo.

        Incluye la barra actual (en formación). Los signal generators deben
        considerar solo barras cerradas — usar `get_closed_bars()` si se
        quiere evitar la barra en formación.
        """
        tf = self._resolve_timeframe(timeframe)

        if self.client.fake:
            return self._fake_bars(symbol, n_bars)

        self.client.ensure_connected()
        rates = self.client.raw.copy_rates_from_pos(symbol, tf, 0, n_bars)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"MT5 no devolvió barras para {symbol} {timeframe}")

        df = pd.DataFrame(rates)
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("datetime")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df.attrs["symbol"] = symbol
        return df

    def get_closed_bars(self, symbol: str, timeframe: str, n_bars: int = 500) -> pd.DataFrame:
        """Descarta la última barra (en formación)."""
        df = self.get_bars(symbol, timeframe, n_bars + 1)
        return df.iloc[:-1].copy()

    def last_tick(self, symbol: str) -> tuple[float, float]:
        """Devuelve (bid, ask) actual — útil para slippage real."""
        if self.client.fake:
            return (2000.0, 2000.4)  # XAUUSD dummy
        tick = self.client.raw.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"No tick para {symbol}")
        return (float(tick.bid), float(tick.ask))

    def _resolve_timeframe(self, tf: str):
        tf = tf.lower()
        if tf not in _TIMEFRAME_MAP:
            raise ValueError(f"Timeframe {tf!r} no soportado")
        if self.client.fake:
            return tf
        return getattr(self.client.raw, _TIMEFRAME_MAP[tf])

    def _fake_bars(self, symbol: str, n_bars: int) -> pd.DataFrame:
        """Genera barras sintéticas para modo FAKE."""
        import numpy as np
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        idx = pd.date_range(end=now, periods=n_bars, freq="1h")
        rng = np.random.default_rng(42)
        base = 2000.0
        rets = rng.normal(0, 0.002, n_bars).cumsum()
        close = base * (1 + rets)
        df = pd.DataFrame({
            "open":  close + rng.normal(0, 2, n_bars),
            "high":  close + np.abs(rng.normal(5, 2, n_bars)),
            "low":   close - np.abs(rng.normal(5, 2, n_bars)),
            "close": close,
            "volume": rng.integers(100, 1000, n_bars),
        }, index=idx)
        df.index.name = "datetime"
        df.attrs["symbol"] = symbol
        return df
