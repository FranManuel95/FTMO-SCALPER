from datetime import datetime

import pandas as pd

from src.data.loaders.base import BaseLoader

SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "XAUUSD": "GC=F",
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
}

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}


class YahooLoader(BaseLoader):
    def load(self, symbol: str, start: datetime, end: datetime, timeframe: str = "1h") -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance not installed. Use local MT5 CSV data or install yfinance.")
        ticker = SYMBOL_MAP.get(symbol.upper(), symbol)
        interval = TIMEFRAME_MAP.get(timeframe, timeframe)

        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=True)

        # yfinance puede retornar MultiIndex de columnas — aplanarlo
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]

        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "datetime"

        return self.validate(df)
