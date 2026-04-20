"""
ICT Fair Value Gap (FVG) Strategy

An FVG (imbalance) forms when 3 consecutive candles create a price gap:
  Bullish FVG: candle[n-2].high < candle[n].low  → gap going UP
    Price later retraces into this zone → LONG (institutional support)
  Bearish FVG: candle[n-2].low > candle[n].high  → gap going DOWN
    Price later retraces into this zone → SHORT (institutional resistance)

Filters:
  - FVG size between min_atr_mult and max_atr_mult of ATR (filters noise and news)
  - ADX > adx_min (trending market, FVGs are more reliable)
  - HTF trend alignment (only long FVGs in H4 bull trend)
  - Session filter (London/NY only)
  - FVG expires after max_bars_to_fill candles
  - Max 1 signal per FVG zone (consumed on first entry)
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_htf_trend


@dataclass
class FVGConfig:
    adx_min: float = 20.0
    rr_target: float = 2.5
    atr_sl_mult: float = 0.5       # SL distance below/above FVG zone edge
    fvg_min_atr: float = 0.1       # minimum FVG size (filters tiny gaps)
    fvg_max_atr: float = 3.0       # maximum FVG size (filters news spikes)
    max_bars_to_fill: int = 48     # FVG expires if not filled within N bars
    max_signals_per_day: int = 2
    tz_offset_hours: int = 2
    session_filter: bool = True    # London + NY (07:00-21:00 UTC)
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200

    @property
    def session_start_h(self) -> int:
        return (7 + self.tz_offset_hours) % 24

    @property
    def session_end_h(self) -> int:
        return (21 + self.tz_offset_hours) % 24


def generate_fvg_signals(
    df: pd.DataFrame,
    config: FVGConfig | None = None,
) -> list[Signal]:
    """
    Generate FVG entry signals.

    FVG detection (no look-ahead):
    - At bar i, look at bars [i-2, i-1, i] to detect FVG formation.
    - Store active FVGs in a list.
    - On each subsequent bar, check if price enters an active FVG zone.
    - Signal generated on bar of entry. FVG consumed (one signal per zone).
    """
    if config is None:
        config = FVGConfig()

    df = df.copy()
    df = add_atr(df, 14)
    df = add_adx(df, 14)

    if config.htf_trend_enabled:
        df = add_htf_trend(
            df,
            htf_resample=config.htf_resample,
            ema_fast=config.htf_ema_fast,
            ema_slow=config.htf_ema_slow,
        )

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    atrs = df["atr_14"].values
    adxs = df["adx_14"].values
    htf_trends = df["htf_trend"].values if config.htf_trend_enabled else np.zeros(len(df))
    timestamps = df.index

    # active_fvgs: list of dicts with zone info and expiry
    active_fvgs: list[dict] = []
    signals: list[Signal] = []
    signals_per_day: dict[str, int] = {}

    symbol = df.attrs.get("symbol", "UNKNOWN")

    for i in range(2, len(df)):
        ts = timestamps[i].to_pydatetime()
        day_key = ts.strftime("%Y-%m-%d")
        hour = ts.hour

        atr = atrs[i]
        adx = adxs[i]
        close = closes[i]
        low = lows[i]
        high = highs[i]

        if np.isnan(atr) or np.isnan(adx):
            continue

        htf_raw = htf_trends[i] if config.htf_trend_enabled else 0.0
        htf = 0 if np.isnan(htf_raw) else int(htf_raw)

        # ── Step 1: detect new FVG at bars [i-2, i-1, i] ──
        h_prev2 = highs[i - 2]
        l_prev2 = lows[i - 2]

        # Bullish FVG: gap between candle[i-2].high and candle[i].low
        if low > h_prev2:
            fvg_size = low - h_prev2
            if config.fvg_min_atr * atr <= fvg_size <= config.fvg_max_atr * atr:
                active_fvgs.append({
                    "side": "LONG",
                    "zone_low": h_prev2,    # bottom of gap
                    "zone_high": low,        # top of gap
                    "created_at": i,
                    "expiry": i + config.max_bars_to_fill,
                })

        # Bearish FVG: gap between candle[i].high and candle[i-2].low
        if high < l_prev2:
            fvg_size = l_prev2 - high
            if config.fvg_min_atr * atr <= fvg_size <= config.fvg_max_atr * atr:
                active_fvgs.append({
                    "side": "SHORT",
                    "zone_low": high,        # bottom of gap
                    "zone_high": l_prev2,    # top of gap
                    "created_at": i,
                    "expiry": i + config.max_bars_to_fill,
                })

        # ── Step 2: check if current bar enters any active FVG ──
        # (only check FVGs created before this bar — no same-bar entry)
        expired = []
        for fvg in active_fvgs:
            if fvg["created_at"] >= i:
                continue  # can't enter FVG on the bar it formed
            if i > fvg["expiry"]:
                expired.append(fvg)
                continue

            entered_zone = (low <= fvg["zone_high"]) and (high >= fvg["zone_low"])
            if not entered_zone:
                continue

            # ── Filters ──
            if adx < config.adx_min:
                expired.append(fvg)  # consume regardless
                continue

            if config.session_filter:
                s, e = config.session_start_h, config.session_end_h
                in_session = (hour >= s and hour < e) if s < e else (hour >= s or hour < e)
                if not in_session:
                    continue  # don't consume — try again next bar in session

            if signals_per_day.get(day_key, 0) >= config.max_signals_per_day:
                continue

            if config.htf_trend_enabled:
                if fvg["side"] == "LONG" and htf < 0:
                    expired.append(fvg)  # counter-trend — discard
                    continue
                if fvg["side"] == "SHORT" and htf > 0:
                    expired.append(fvg)  # counter-trend — discard
                    continue

            # ── Build signal ──
            if fvg["side"] == "LONG":
                sl = fvg["zone_low"] - atr * config.atr_sl_mult
                risk = close - sl
                if risk <= 0:
                    expired.append(fvg)
                    continue
                tp = close + risk * config.rr_target
                side = Side.LONG
            else:
                sl = fvg["zone_high"] + atr * config.atr_sl_mult
                risk = sl - close
                if risk <= 0:
                    expired.append(fvg)
                    continue
                tp = close - risk * config.rr_target
                side = Side.SHORT

            signals.append(Signal(
                symbol=symbol,
                side=side,
                signal_type=SignalType.BREAKOUT,  # closest existing type
                timestamp=ts,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            ))

            signals_per_day[day_key] = signals_per_day.get(day_key, 0) + 1
            expired.append(fvg)  # consume — one signal per FVG

        for fvg in expired:
            if fvg in active_fvgs:
                active_fvgs.remove(fvg)

    return signals
