# strategy/signal_engine.py — Breakout + Momentum + EMA Trend

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

class SignalEngine:
    LONDON_OPEN  = time(7, 0)
    LONDON_CLOSE = time(17, 0)

    RANGE_PERIOD  = 20
    EMA_FAST      = 9
    EMA_SLOW      = 21
    EMA_TREND     = 200
    RSI_PERIOD    = 14
    ATR_PERIOD    = 14
    ATR_SL_MULT   = 1.5
    RR_RATIO      = 2.0
    ATR_MIN       = 0.0003
    BREAKOUT_CONF = 0.0002  # Minimo pips de ruptura para confirmar

    def is_valid_session(self) -> bool:
        now = datetime.utcnow().time()
        return self.LONDON_OPEN <= now <= self.LONDON_CLOSE

    def _compute_rsi(self, prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        gain  = delta.where(delta > 0, 0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(self.RSI_PERIOD).mean()
        rs    = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))

    def _compute_atr(self, df: pd.DataFrame) -> pd.Series:
        hl  = df['high'] - df['low']
        hcp = abs(df['high'] - df['close'].shift())
        lcp = abs(df['low']  - df['close'].shift())
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        return tr.rolling(self.ATR_PERIOD).mean()

    def analyze(self, df: pd.DataFrame) -> TradeSetup:
        if not self.is_valid_session():
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Fuera de sesion")

        if len(df) < self.EMA_TREND + 10:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Pocas velas")

        close    = df['close']
        high     = df['high']
        low      = df['low']
        open_    = df['open']

        rsi       = self._compute_rsi(close)
        atr       = self._compute_atr(df)
        ema_fast  = close.ewm(span=self.EMA_FAST,  adjust=False).mean()
        ema_slow  = close.ewm(span=self.EMA_SLOW,  adjust=False).mean()
        ema_trend = close.ewm(span=self.EMA_TREND, adjust=False).mean()

        curr_close = float(close.iloc[-1])
        curr_open  = float(open_.iloc[-1])
        curr_high  = float(high.iloc[-1])
        curr_low   = float(low.iloc[-1])
        curr_rsi   = float(rsi.iloc[-1])
        curr_atr   = float(atr.iloc[-1])
        curr_trend = float(ema_trend.iloc[-1])
        curr_fast  = float(ema_fast.iloc[-1])
        curr_slow  = float(ema_slow.iloc[-1])

        sl_pips = curr_atr * self.ATR_SL_MULT / 0.0001

        if curr_atr < self.ATR_MIN:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "ATR bajo")

        # Rango de las ultimas N velas (sin incluir la actual)
        range_high = float(high.iloc[-self.RANGE_PERIOD-1:-1].max())
        range_low  = float(low.iloc[-self.RANGE_PERIOD-1:-1].min())

        # Fuerza de la vela actual
        candle_body  = abs(curr_close - curr_open)
        candle_range = curr_high - curr_low
        body_ratio   = candle_body / (candle_range + 1e-10)

        # EMA momentum
        ema_bullish = curr_fast > curr_slow
        ema_bearish = curr_fast < curr_slow

        # --- SEÑAL BUY ---
        # Ruptura del maximo del rango + vela alcista fuerte + tendencia alcista
        breakout_up = curr_close > range_high + self.BREAKOUT_CONF
        candle_bull = curr_close > curr_open and body_ratio > 0.5
        trend_up    = curr_close > curr_trend and ema_bullish
        rsi_ok_buy  = 40 < curr_rsi < 75

        if breakout_up and candle_bull and trend_up and rsi_ok_buy:
            sl = range_high - curr_atr * 0.5
            tp = curr_close + (curr_close - sl) * self.RR_RATIO
            return TradeSetup(
                Signal.BUY, curr_close, sl, tp, sl_pips, self.RR_RATIO,
                f"BUY | Breakout {range_high:.5f} | RSI={curr_rsi:.1f}"
            )

        # --- SEÑAL SELL ---
        # Ruptura del minimo del rango + vela bajista fuerte + tendencia bajista
        breakout_down = curr_close < range_low - self.BREAKOUT_CONF
        candle_bear   = curr_close < curr_open and body_ratio > 0.5
        trend_down    = curr_close < curr_trend and ema_bearish
        rsi_ok_sell   = 25 < curr_rsi < 60

        if breakout_down and candle_bear and trend_down and rsi_ok_sell:
            sl = range_low + curr_atr * 0.5
            tp = curr_close - (sl - curr_close) * self.RR_RATIO
            return TradeSetup(
                Signal.SELL, curr_close, sl, tp, sl_pips, self.RR_RATIO,
                f"SELL | Breakout {range_low:.5f} | RSI={curr_rsi:.1f}"
            )

        return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Sin breakout")