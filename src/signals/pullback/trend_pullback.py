from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr, add_ema, add_rsi
from src.features.trend.htf_filter import add_daily_trend, add_htf_adx, add_htf_trend, add_weekly_regime


@dataclass
class TrendPullbackConfig:
    ema_trend: int = 50
    ema_fast: int = 20
    adx_min: float = 20.0
    rsi_oversold: float = 40.0
    rsi_overbought: float = 60.0
    rr_target: float = 2.0
    atr_sl_mult: float = 1.5
    max_signals_per_day: int = 2
    session_filter: bool = True
    tz_offset_hours: int = 2
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200
    # Filtro de régimen: ADX en timeframe diario
    daily_adx_min: float = 0.0   # 0 = desactivado; ej: 20.0 activa el filtro
    daily_adx_length: int = 14
    # Filtro macro: EMA semanal — solo operar en dirección del régimen macro
    weekly_regime_enabled: bool = False
    weekly_ema_period: int = 50
    # Filtro de régimen diario: EMA50 vs EMA200 daily (golden/death cross)
    daily_trend_enabled: bool = False


def generate_pullback_signals(
    df: pd.DataFrame,
    config: TrendPullbackConfig | None = None,
) -> list[Signal]:
    if config is None:
        config = TrendPullbackConfig()

    df = df.copy()
    df = add_ema(df, [config.ema_fast, config.ema_trend])
    df = add_adx(df, 14)
    df = add_atr(df, 14)
    df = add_rsi(df, 14)

    if config.htf_trend_enabled:
        df = add_htf_trend(df, htf_resample=config.htf_resample,
                           ema_fast=config.htf_ema_fast, ema_slow=config.htf_ema_slow)

    daily_adx_enabled = config.daily_adx_min > 0
    if daily_adx_enabled:
        df = add_htf_adx(df, htf_resample="1D", adx_length=config.daily_adx_length)

    if config.weekly_regime_enabled:
        df = add_weekly_regime(df, ema_period=config.weekly_ema_period)

    if config.daily_trend_enabled:
        df = add_daily_trend(df)

    # Pre-extraer arrays para evitar df.iloc[i] (muy lento con muchas columnas)
    ema_f_key = f"ema_{config.ema_fast}"
    ema_t_key = f"ema_{config.ema_trend}"
    daily_adx_col = f"htf_adx_{config.daily_adx_length}"

    timestamps = df.index.to_pydatetime()
    hours = df.index.hour
    close_arr = df["close"].values
    ema_f = df[ema_f_key].values
    ema_t = df[ema_t_key].values
    adx_arr = df["adx_14"].values
    atr_arr = df["atr_14"].values
    rsi_arr = df["rsi_14"].values
    htf_arr = df["htf_trend"].values if config.htf_trend_enabled else np.zeros(len(df))
    daily_adx_arr = df[daily_adx_col].values if daily_adx_enabled else np.full(len(df), 999.0)
    weekly_regime_arr = df["weekly_regime"].values if config.weekly_regime_enabled else np.zeros(len(df))
    daily_trend_arr = df["daily_trend"].values if config.daily_trend_enabled else np.zeros(len(df))

    # Horas de sesión activa en broker time
    s_start = (7 + config.tz_offset_hours) % 24
    s_end = (21 + config.tz_offset_hours) % 24

    symbol = df.attrs.get("symbol", "UNKNOWN")
    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    for i in range(2, len(df)):
        hour = hours[i]

        # Filtro sesión
        if config.session_filter:
            if s_start < s_end:
                if not (s_start <= hour < s_end):
                    continue
            else:
                if not (hour >= s_start or hour < s_end):
                    continue

        ts = timestamps[i]
        day_key = ts.strftime("%Y-%m-%d")

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        # Validar NaN
        if np.isnan(ema_f[i]) or np.isnan(ema_t[i]) or np.isnan(adx_arr[i]) or np.isnan(atr_arr[i]) or np.isnan(rsi_arr[i]):
            continue

        if adx_arr[i] < config.adx_min:
            continue

        # Filtro régimen diario
        if daily_adx_enabled and (np.isnan(daily_adx_arr[i]) or daily_adx_arr[i] < config.daily_adx_min):
            continue

        close = close_arr[i]
        prev_close = close_arr[i - 1]
        atr = atr_arr[i]

        bullish = close > ema_t[i] and ema_f[i] > ema_t[i]
        bearish = close < ema_t[i] and ema_f[i] < ema_t[i]

        # Filtro régimen semanal: solo operar en dirección del macro trend
        if config.weekly_regime_enabled and not np.isnan(weekly_regime_arr[i]):
            wr = weekly_regime_arr[i]
            if wr > 0 and bearish:   # régimen alcista → bloquear shorts
                continue
            if wr < 0 and bullish:   # régimen bajista → bloquear longs
                continue

        # Filtro régimen diario: EMA50 vs EMA200 daily (golden/death cross)
        if config.daily_trend_enabled:
            dt = int(daily_trend_arr[i])
            if dt > 0 and bearish:   # golden cross → solo longs
                continue
            if dt < 0 and bullish:   # death cross → solo shorts
                continue

        # Filtro H4
        if config.htf_trend_enabled:
            htf = int(htf_arr[i]) if not np.isnan(htf_arr[i]) else 0
            if bullish and htf < 0:
                continue
            if bearish and htf > 0:
                continue

        if bullish:
            pullback = prev_close < ema_f[i - 1] and close > ema_f[i]
            rsi_ok = rsi_arr[i] < config.rsi_overbought
            if pullback and rsi_ok:
                sl = close - atr * config.atr_sl_mult
                risk = close - sl
                tp = close + risk * config.rr_target
                signals.append(Signal(symbol=symbol, side=Side.LONG,
                    signal_type=SignalType.PULLBACK, timestamp=ts,
                    entry_price=close, stop_loss=sl, take_profit=tp))
                signals_today[day_key] = signals_today.get(day_key, 0) + 1

        elif bearish:
            pullback = prev_close > ema_f[i - 1] and close < ema_f[i]
            rsi_ok = rsi_arr[i] > config.rsi_oversold
            if pullback and rsi_ok:
                sl = close + atr * config.atr_sl_mult
                risk = sl - close
                tp = close - risk * config.rr_target
                signals.append(Signal(symbol=symbol, side=Side.SHORT,
                    signal_type=SignalType.PULLBACK, timestamp=ts,
                    entry_price=close, stop_loss=sl, take_profit=tp))
                signals_today[day_key] = signals_today.get(day_key, 0) + 1

    return signals
