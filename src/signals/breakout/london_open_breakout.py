"""
London Open Range Breakout (ORB) Strategy

London open (07:00-08:00 UTC) is the first high-liquidity session for XAUUSD.
European institutional flow dominates gold price direction for the London morning.

Logic:
  1. Build range from first hour of London open (07:00-08:00 UTC = 09:00-10:00 broker)
  2. Trade breakout of the range in direction of H4 trend
  3. Entry window: 08:00-12:00 UTC (core London session, before NY overlap dilutes signal)

Difference from NY ORB:
  - Earlier in the day (London only, before NY adds volume)
  - More pure "European institutional" price action
  - Combined with NY ORB: two non-overlapping daily setups
"""
from dataclasses import dataclass

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_daily_trend, add_htf_trend


@dataclass
class LondonOpenBreakoutConfig:
    adx_min: float = 18.0
    rr_target: float = 2.5
    atr_sl_mult: float = 0.3
    range_min_atr: float = 0.3
    range_max_atr: float = 3.5
    max_signals_per_day: int = 1
    tz_offset_hours: int = 2
    # London open range: 07:00-08:00 UTC = 09:00-10:00 broker (UTC+2)
    range_start_utc: int = 7
    range_end_utc: int = 8
    # Entry window: 08:00-12:00 UTC = 10:00-14:00 broker
    entry_start_utc: int = 8
    entry_end_utc: int = 12
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200
    daily_trend_enabled: bool = False


def generate_london_open_breakout_signals(
    df: pd.DataFrame,
    config: LondonOpenBreakoutConfig | None = None,
) -> list[Signal]:
    if config is None:
        config = LondonOpenBreakoutConfig()

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

    if config.daily_trend_enabled:
        df = add_daily_trend(df)

    tz = config.tz_offset_hours
    range_start_h = (config.range_start_utc + tz) % 24   # 9  broker
    range_end_h   = (config.range_end_utc   + tz) % 24   # 10 broker
    entry_start_h = (config.entry_start_utc + tz) % 24   # 10 broker
    entry_end_h   = (config.entry_end_utc   + tz) % 24   # 14 broker

    signals: list[Signal] = []
    symbol = df.attrs.get("symbol", "UNKNOWN")
    daily_range: dict[str, dict] = {}

    for i in range(len(df)):
        ts  = df.index[i].to_pydatetime()
        row = df.iloc[i]
        day_key = ts.strftime("%Y-%m-%d")
        hour    = ts.hour
        minute  = ts.minute

        bar_mins       = hour * 60 + minute
        range_start_m  = range_start_h * 60
        range_end_m    = range_end_h   * 60
        entry_start_m  = entry_start_h * 60
        entry_end_m    = entry_end_h   * 60

        # ── Build range ──
        if range_start_m <= bar_mins < range_end_m:
            if day_key not in daily_range:
                daily_range[day_key] = {"high": row["high"], "low": row["low"], "built": False}
            else:
                daily_range[day_key]["high"] = max(daily_range[day_key]["high"], row["high"])
                daily_range[day_key]["low"]  = min(daily_range[day_key]["low"],  row["low"])

        if bar_mins >= range_end_m and day_key in daily_range:
            daily_range[day_key]["built"] = True

        if day_key not in daily_range or not daily_range[day_key].get("built"):
            continue

        if not (entry_start_m <= bar_mins < entry_end_m):
            continue

        if daily_range[day_key].get("signalled"):
            continue

        rng        = daily_range[day_key]
        range_high = rng["high"]
        range_low  = rng["low"]
        range_size = range_high - range_low

        import pandas as _pd
        atr    = row.get("atr_14")
        adx    = row.get("adx_14")
        close  = row["close"]
        htf_raw = row.get("htf_trend", 0) if config.htf_trend_enabled else 0
        dt_raw  = row.get("daily_trend", 0) if config.daily_trend_enabled else 0

        nan_check = [atr, adx, close]
        if config.htf_trend_enabled:
            nan_check.append(htf_raw)
        if config.daily_trend_enabled:
            nan_check.append(dt_raw)
        if any(_pd.isna(v) for v in nan_check):
            continue

        htf = int(htf_raw)
        dt  = int(dt_raw)

        if adx < config.adx_min:
            continue
        if range_size < atr * config.range_min_atr:
            continue
        if range_size > atr * config.range_max_atr:
            continue

        is_long  = close > range_high
        is_short = close < range_low

        if not is_long and not is_short:
            continue

        if config.htf_trend_enabled:
            if is_long  and htf < 0: continue
            if is_short and htf > 0: continue

        if config.daily_trend_enabled:
            if is_long  and dt < 0: continue
            if is_short and dt > 0: continue

        buffer = atr * config.atr_sl_mult

        if is_long:
            sl   = range_low - buffer
            risk = close - sl
            if risk <= 0: continue
            tp   = close + risk * config.rr_target
            side = Side.LONG
        else:
            sl   = range_high + buffer
            risk = sl - close
            if risk <= 0: continue
            tp   = close - risk * config.rr_target
            side = Side.SHORT

        signals.append(Signal(
            symbol=symbol, side=side,
            signal_type=SignalType.BREAKOUT,
            timestamp=ts, entry_price=close,
            stop_loss=sl, take_profit=tp,
        ))
        daily_range[day_key]["signalled"] = True

    return signals
