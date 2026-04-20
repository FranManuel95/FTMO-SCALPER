"""
Asian Session ORB (Opening Range Breakout) Strategy

The Asian session (23:00-07:00 UTC) establishes a range during the quietest part of
the 24h FX cycle. When the London/European session opens and breaks that range, it
often signals the direction for the day — especially for JPY pairs driven by
carry-trade and macro flows.

Logic:
  1. Build range from Asian session: 23:00 UTC (prev day) → 07:00 UTC (current day)
  2. Trade breakout of the range in direction of H4 trend
  3. Entry window: 07:00-12:00 UTC (London open until NY overlap)
  4. SL = opposite side of range + 0.1×ATR buffer
  5. TP = entry ± RR × stop_distance
  6. Trail: applied externally in run_backtest exit loop (trail_atr_mult parameter)

Why Asian ORB works on USDJPY:
  - JPY crosses are most active in Asian session, building a meaningful range
  - London open often breaks the Asian range with fresh European institutional flow
  - Carry-trade dynamics give strong directional bias visible in H4 trend
  - Low spread on JPY pairs makes tight ranges viable
"""
from dataclasses import dataclass

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_daily_trend, add_htf_trend


@dataclass
class AsianSessionORBConfig:
    adx_min: float = 18.0
    rr_target: float = 2.5
    atr_sl_mult: float = 0.1          # extra buffer beyond range edge for SL
    range_min_atr: float = 0.5        # minimum range size (filter flat sessions)
    range_max_atr: float = 4.0        # maximum range size (filter news gaps)
    max_signals_per_day: int = 1
    tz_offset_hours: int = 2
    # Asian session range build window (UTC times)
    # Asian session: 23:00 UTC (prev day) → 07:00 UTC (current day)
    # In broker UTC+2: 01:00 → 09:00
    asian_end_hour_utc: int = 7       # Asian session ends at 07:00 UTC
    # Entry window: London open until NY overlap
    entry_start_utc: int = 7          # 07:00 UTC = 09:00 broker
    entry_end_utc: int = 12           # 12:00 UTC = 14:00 broker
    # HTF trend filter
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200
    # Daily trend filter
    daily_trend_enabled: bool = False


def generate_asian_session_orb_signals(
    df: pd.DataFrame,
    config: AsianSessionORBConfig | None = None,
) -> list[Signal]:
    """
    Build the Asian session opening range (23:00-07:00 UTC) and trade the breakout.

    The Asian range is accumulated bar-by-bar: bars from 23:00 UTC the previous day
    up to (but not including) 07:00 UTC the current day. The range is assigned to
    the *current* trading day (the day of the 07:00 UTC boundary).

    Entry is triggered on the first bar that closes outside the range during the
    entry window (07:00-12:00 UTC). One signal per day.
    """
    if config is None:
        config = AsianSessionORBConfig()

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
    # Convert UTC boundaries to broker local time (UTC+tz)
    asian_end_h  = (config.asian_end_hour_utc + tz) % 24   # 09:00 broker
    entry_start_h = (config.entry_start_utc + tz) % 24     # 09:00 broker
    entry_end_h   = (config.entry_end_utc   + tz) % 24     # 14:00 broker

    # Asian session starts at 23:00 UTC = 01:00 broker.
    # Bars with broker hour in [01:00, 09:00) belong to the Asian range.
    # Since 23:00 UTC wraps to 01:00 broker, bars at hour 0 (midnight broker)
    # are outside the Asian session (they are the 22:00 UTC bar).
    # Asian range hours in broker time: 1, 2, 3, 4, 5, 6, 7, 8  (i.e. < asian_end_h)
    # and also hour 0 is excluded (it maps to 22:00 UTC, pre-Asian).
    # So: (1 <= broker_hour < asian_end_h) OR broker_hour == 0 is NOT Asian.
    # But hour 23 broker = 21:00 UTC also not Asian. Hour 0 broker = 22:00 UTC not Asian.
    # Asian in broker: hours 1..8 (1 <= h < 9)
    asian_session_start_broker = 1   # 23:00 UTC → 01:00 broker

    signals: list[Signal] = []
    symbol = df.attrs.get("symbol", "UNKNOWN")

    # daily_range keyed by the *entry* date (the day on which 07:00 UTC falls)
    # Each entry: {high, low, built, signalled}
    daily_range: dict[str, dict] = {}

    for i in range(len(df)):
        ts  = df.index[i].to_pydatetime()
        row = df.iloc[i]

        # Broker local hour/minute
        broker_hour   = (ts.hour + tz) % 24
        broker_minute = ts.minute

        bar_broker_mins = broker_hour * 60 + broker_minute

        # Determine the "trading day" this bar belongs to for range building.
        # Asian session bars (01:00-08:59 broker) belong to the SAME calendar date
        # as their broker timestamp (the range will be consumed that day starting 09:00).
        # After 09:00 broker (entry/post-range), they belong to the same calendar day.
        # The only subtlety: broker date from the UTC timestamp.
        import datetime as _dt
        broker_dt = ts.astimezone(_dt.timezone((_dt.timedelta(hours=tz))))
        day_key = broker_dt.strftime("%Y-%m-%d")

        # ── Accumulate Asian session range ──
        # Bars in broker hours [1, asian_end_h) build the range for `day_key`
        in_asian_window = (
            asian_session_start_broker <= broker_hour < asian_end_h
        )
        if in_asian_window:
            if day_key not in daily_range:
                daily_range[day_key] = {
                    "high": row["high"],
                    "low": row["low"],
                    "built": False,
                    "signalled": False,
                }
            else:
                daily_range[day_key]["high"] = max(daily_range[day_key]["high"], row["high"])
                daily_range[day_key]["low"]  = min(daily_range[day_key]["low"],  row["low"])

        # Mark range as built once we reach or pass asian_end_h (09:00 broker)
        if broker_hour >= asian_end_h and day_key in daily_range:
            daily_range[day_key]["built"] = True

        # ── Entry window guard ──
        if day_key not in daily_range or not daily_range[day_key].get("built"):
            continue

        entry_start_mins = entry_start_h * 60
        entry_end_mins   = entry_end_h   * 60

        if not (entry_start_mins <= bar_broker_mins < entry_end_mins):
            continue

        if daily_range[day_key].get("signalled"):
            continue

        rng        = daily_range[day_key]
        range_high = rng["high"]
        range_low  = rng["low"]
        range_size = range_high - range_low

        import pandas as _pd
        atr   = row.get("atr_14")
        adx   = row.get("adx_14")
        close = row["close"]
        htf   = int(row.get("htf_trend", 0)) if config.htf_trend_enabled else 0
        dt    = int(row.get("daily_trend", 0)) if config.daily_trend_enabled else 0

        if any(_pd.isna(v) for v in [atr, adx, close]):
            continue

        # ── Filters ──
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
