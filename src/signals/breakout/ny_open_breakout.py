"""
NY Open Range Breakout (ORB) Strategy

The NY session open (13:30-14:00 UTC) is the highest-volume window for XAUUSD.
Strategy:
  1. Build the opening range from the first 30 min of NY session (13:30-14:00 UTC)
  2. Trade the breakout in the direction of the HTF trend
  3. SL = opposite side of range + ATR buffer
  4. TP = entry ± range_size * rr_mult (or fixed RR)

Why NY ORB differs from Asian/London breakout:
  - NY open is the most liquid time for XAUUSD (NY + London overlap)
  - 30-min range is shorter → tighter SL, better R:R
  - Institutional order flow is highest at NY open
  - Range is "fresh" — built after Asia + London price discovery
"""
from dataclasses import dataclass

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_daily_trend, add_htf_trend


@dataclass
class NYOpenBreakoutConfig:
    adx_min: float = 18.0
    rr_target: float = 2.5
    atr_sl_mult: float = 0.3         # extra buffer beyond range edge for SL
    range_min_atr: float = 0.3       # minimum range size (filter flat opens)
    range_max_atr: float = 3.5       # maximum range size (filter news gaps)
    max_signals_per_day: int = 1
    tz_offset_hours: int = 2
    # NY open range build window (UTC times, converted to broker tz internally)
    # NY open range window (UTC real times). On 1H data the bar at 13:00 UTC
    # (= 15:00 broker/stored) contains the NY open (13:30 UTC). Using :00 aligns
    # with 1H bar boundaries.  For 15M data keep range_start_min=30.
    range_start_utc: int = 13        # hour of range start (UTC)
    range_start_min: int = 0         # use 0 for 1H data (bar alignment), 30 for 15M
    range_end_utc: int = 14          # hour of range end (UTC)
    range_end_min: int = 0
    # Trade entry window (UTC): after range is complete until end of NY session
    entry_start_utc: int = 14
    entry_end_utc: int = 20
    # HTF trend filter
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200
    # Daily trend filter
    daily_trend_enabled: bool = False


def generate_ny_open_breakout_signals(
    df: pd.DataFrame,
    config: NYOpenBreakoutConfig | None = None,
) -> list[Signal]:
    """
    Build the NY opening range (30 min) and trade the breakout.

    Range is built from bars whose UTC time falls in [range_start, range_end).
    Entry triggered on first close outside the range during the entry window.
    One signal per day.
    """
    if config is None:
        config = NYOpenBreakoutConfig()

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
    # Convert UTC times to broker local (UTC+tz)
    range_start_h = (config.range_start_utc + tz) % 24
    range_start_m = config.range_start_min
    range_end_h = (config.range_end_utc + tz) % 24
    range_end_m = config.range_end_min
    entry_start_h = (config.entry_start_utc + tz) % 24
    entry_end_h = (config.entry_end_utc + tz) % 24

    signals: list[Signal] = []
    symbol = df.attrs.get("symbol", "UNKNOWN")

    # Group by date to build daily range
    daily_range: dict[str, dict] = {}  # date → {high, low, built}

    for i in range(len(df)):
        ts = df.index[i].to_pydatetime()
        row = df.iloc[i]
        day_key = ts.strftime("%Y-%m-%d")
        hour = ts.hour
        minute = ts.minute

        bar_minutes = hour * 60 + minute
        range_start_mins = range_start_h * 60 + range_start_m
        range_end_mins = range_end_h * 60 + range_end_m
        entry_start_mins = entry_start_h * 60
        entry_end_mins = entry_end_h * 60

        # ── Build the opening range ──
        in_range_window = range_start_mins <= bar_minutes < range_end_mins
        if in_range_window:
            if day_key not in daily_range:
                daily_range[day_key] = {"high": row["high"], "low": row["low"], "built": False}
            else:
                daily_range[day_key]["high"] = max(daily_range[day_key]["high"], row["high"])
                daily_range[day_key]["low"] = min(daily_range[day_key]["low"], row["low"])

        # Mark range as built once we pass the range_end time
        if bar_minutes >= range_end_mins and day_key in daily_range:
            daily_range[day_key]["built"] = True

        # ── Entry window: look for breakout ──
        if day_key not in daily_range or not daily_range[day_key].get("built"):
            continue

        if not (entry_start_mins <= bar_minutes < entry_end_mins):
            continue

        # Skip if already signalled today
        if daily_range[day_key].get("signalled"):
            continue

        rng = daily_range[day_key]
        range_high = rng["high"]
        range_low = rng["low"]
        range_size = range_high - range_low

        atr = row.get("atr_14")
        adx = row.get("adx_14")
        close = row["close"]
        htf_trend = int(row.get("htf_trend", 0)) if config.htf_trend_enabled else 0
        daily_trend = int(row.get("daily_trend", 0)) if config.daily_trend_enabled else 0

        import pandas as _pd
        if any(_pd.isna(v) for v in [atr, adx, close]):
            continue

        # ── Filters ──
        if adx < config.adx_min:
            continue

        if range_size < atr * config.range_min_atr:
            continue

        if range_size > atr * config.range_max_atr:
            continue

        is_long_break = close > range_high
        is_short_break = close < range_low

        if not is_long_break and not is_short_break:
            continue

        if config.htf_trend_enabled:
            if is_long_break and htf_trend < 0:
                continue
            if is_short_break and htf_trend > 0:
                continue

        if config.daily_trend_enabled:
            if is_long_break and daily_trend < 0:
                continue
            if is_short_break and daily_trend > 0:
                continue

        buffer = atr * config.atr_sl_mult

        if is_long_break:
            sl = range_low - buffer
            risk = close - sl
            if risk <= 0:
                continue
            tp = close + risk * config.rr_target
            side = Side.LONG
        else:
            sl = range_high + buffer
            risk = sl - close
            if risk <= 0:
                continue
            tp = close - risk * config.rr_target
            side = Side.SHORT

        signals.append(Signal(
            symbol=symbol,
            side=side,
            signal_type=SignalType.BREAKOUT,
            timestamp=ts,
            entry_price=close,
            stop_loss=sl,
            take_profit=tp,
        ))

        daily_range[day_key]["signalled"] = True

    return signals
