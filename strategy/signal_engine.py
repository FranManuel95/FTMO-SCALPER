# strategy/signal_engine.py — MTF v2: 1H + 15M + 5M + VWAP + ADX + Trailing

import pandas as pd
import numpy as np
from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum

class Signal(Enum):
    BUY  = "BUY"
    SELL = "SELL"
    NONE = "NONE"

@dataclass
class TradeSetup:
    signal:      Signal
    entry_price: float
    stop_loss:   float
    take_profit: float
    sl_pips:     float
    rr_ratio:    float
    reason:      str
    trail_mult:  float = 2.0

class SignalEngine:
    LONDON_OPEN  = time(7, 0)
    LONDON_CLOSE = time(17, 0)

    # Parametros validados en backtest
    EMA_TREND   = 200
    EMA_FAST    = 20
    EMA_SLOW    = 50
    ADX_PERIOD  = 14
    ADX_MIN     = 18
    ADX_MAX     = 58
    RSI_PERIOD  = 14
    ATR_PERIOD  = 14
    ATR_SL_MULT = 1.2
    RR_RATIO    = 1.6
    ATR_MIN     = 0.0003
    TRAIL_MULT  = 2.0

    def __init__(self):
        # Cache para datos multi-timeframe
        self._df_1h  = None
        self._df_15m = None

    def is_valid_session(self) -> bool:
        now = datetime.utcnow().time()
        return self.LONDON_OPEN <= now <= self.LONDON_CLOSE

    def update_higher_timeframes(self, df_1h: pd.DataFrame,
                                  df_15m: pd.DataFrame):
        self._df_1h  = self._prepare_1h(df_1h)
        self._df_15m = self._prepare_15m(df_15m)

    def _add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        high  = df['high']
        low   = df['low']
        close = df['close']
        plus_dm  = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0]   = 0
        minus_dm[minus_dm < 0] = 0
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr      = tr.rolling(self.ADX_PERIOD).mean()
        plus_di  = 100 * plus_dm.rolling(self.ADX_PERIOD).mean()  / (atr + 1e-10)
        minus_di = 100 * minus_dm.rolling(self.ADX_PERIOD).mean() / (atr + 1e-10)
        dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        df['adx']      = dx.rolling(self.ADX_PERIOD).mean()
        df['plus_di']  = plus_di
        df['minus_di'] = minus_di
        return df

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        delta = df['close'].diff()
        gain  = delta.where(delta > 0, 0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(self.RSI_PERIOD).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        return df

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        hl  = df['high'] - df['low']
        hcp = abs(df['high'] - df['close'].shift())
        lcp = abs(df['low']  - df['close'].shift())
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.ATR_PERIOD).mean()
        return df

    def _add_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        df['vwap'] = df['close'].ewm(span=20, adjust=False).mean()
        return df

    def _prepare_1h(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df['close']
        df['ema200'] = close.ewm(span=self.EMA_TREND, adjust=False).mean()
        df = self._add_adx(df)
        trend_regime = (df['adx'] > self.ADX_MIN) & (df['adx'] < self.ADX_MAX)
        df['bias_bull'] = (
            (close > df['ema200']) &
            trend_regime &
            (df['plus_di'] > df['minus_di'])
        )
        df['bias_bear'] = (
            (close < df['ema200']) &
            trend_regime &
            (df['minus_di'] > df['plus_di'])
        )
        return df.dropna()

    def _prepare_15m(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df['close']
        df['ema20'] = close.ewm(span=self.EMA_FAST, adjust=False).mean()
        df['ema50'] = close.ewm(span=self.EMA_SLOW, adjust=False).mean()
        df = self._add_rsi(df)
        df = self._add_vwap(df)
        df['setup_bull'] = (
            (df['ema20'] > df['ema50']) &
            (df['rsi'] > 45) & (df['rsi'] < 75) &
            (close > df['vwap'] * 0.9998)
        )
        df['setup_bear'] = (
            (df['ema20'] < df['ema50']) &
            (df['rsi'] < 55) & (df['rsi'] > 25) &
            (close < df['vwap'] * 1.0002)
        )
        return df.dropna()

    def analyze(self, df_5m: pd.DataFrame) -> TradeSetup:
        none = TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Sin senal")

        if not self.is_valid_session():
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Fuera de sesion")

        if self._df_1h is None or self._df_15m is None:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Sin datos HTF")

        if len(df_5m) < 30:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Pocas velas 5M")

        # Preparar 5M
        df = df_5m.copy()
        df = self._add_atr(df)
        close = df['close']
        df['ema9']  = close.ewm(span=9,  adjust=False).mean()
        df['ema21'] = close.ewm(span=21, adjust=False).mean()
        df = df.dropna()

        if len(df) < 3:
            return none

        curr_atr  = float(df['atr'].iloc[-1])
        if curr_atr < self.ATR_MIN:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "ATR bajo")

        # Cruce EMA 9/21 en 5M
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        ema9_up   = float(prev['ema9']) <= float(prev['ema21']) and \
                    float(curr['ema9']) >  float(curr['ema21'])
        ema9_down = float(prev['ema9']) >= float(prev['ema21']) and \
                    float(curr['ema9']) <  float(curr['ema21'])

        # Contexto 1H
        ts     = df.index[-1]
        idx_1h = self._df_1h.index.searchsorted(ts) - 1
        if idx_1h < 0 or idx_1h >= len(self._df_1h):
            return none
        row_1h = self._df_1h.iloc[idx_1h]

        # Setup 15M
        idx_15m = self._df_15m.index.searchsorted(ts) - 1
        if idx_15m < 0 or idx_15m >= len(self._df_15m):
            return none
        row_15m = self._df_15m.iloc[idx_15m]

        entry   = float(curr['close'])
        sl_pips = curr_atr * self.ATR_SL_MULT / 0.0001

        # BUY
        if row_1h['bias_bull'] and row_15m['setup_bull'] and ema9_up:
            sl = entry - curr_atr * self.ATR_SL_MULT
            tp = entry + curr_atr * self.ATR_SL_MULT * self.RR_RATIO
            return TradeSetup(
                Signal.BUY, entry, sl, tp, sl_pips, self.RR_RATIO,
                f"BUY | 1H ADX={row_1h['adx']:.0f} | 15M RSI={row_15m['rsi']:.0f} | EMA9 cross",
                self.TRAIL_MULT
            )

        # SELL
        if row_1h['bias_bear'] and row_15m['setup_bear'] and ema9_down:
            sl = entry + curr_atr * self.ATR_SL_MULT
            tp = entry - curr_atr * self.ATR_SL_MULT * self.RR_RATIO
            return TradeSetup(
                Signal.SELL, entry, sl, tp, sl_pips, self.RR_RATIO,
                f"SELL | 1H ADX={row_1h['adx']:.0f} | 15M RSI={row_15m['rsi']:.0f} | EMA9 cross",
                self.TRAIL_MULT
            )

        return none