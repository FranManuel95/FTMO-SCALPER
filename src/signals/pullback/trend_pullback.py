from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr, add_ema, add_rsi
from src.features.trend.htf_filter import add_htf_trend


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
    # Filtro de sesión: solo operar durante horas activas (London + NY)
    session_filter: bool = True
    session_start_h: int = 9    # London open (broker time)
    session_end_h: int = 22     # NY close (broker time)
    tz_offset_hours: int = 2
    # Filtro tendencia H4
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200


def generate_pullback_signals(
    df: pd.DataFrame,
    config: TrendPullbackConfig | None = None,
) -> list[Signal]:
    """
    Pullback en tendencia con filtro de sesión y confirmación H4.

    Filtros:
    1. Sesión: solo London + NY (evita ruido asiático)
    2. Tendencia 15m: EMA20 > EMA50, precio > EMA50 (alcista) o viceversa
    3. Tendencia H4: confirma dirección en timeframe superior
    4. ADX > mínimo: confirma tendencia activa
    5. Pullback: precio retoca EMA20 y rebota
    6. RSI: no sobrecomprado (long) / no sobrevendido (short)
    """
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

    # Calcular horas de sesión activa en broker time
    if config.session_filter:
        s_start = (7 + config.tz_offset_hours) % 24   # London open
        s_end = (21 + config.tz_offset_hours) % 24     # NY close

    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    ema_f = f"ema_{config.ema_fast}"
    ema_t = f"ema_{config.ema_trend}"

    for i in range(2, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        ts: datetime = row.name.to_pydatetime()
        hour = ts.hour
        day_key = ts.strftime("%Y-%m-%d")

        # Filtro de sesión: solo operar en London + NY
        if config.session_filter:
            if s_start < s_end:
                in_session = s_start <= hour < s_end
            else:
                in_session = hour >= s_start or hour < s_end
            if not in_session:
                continue

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        # Validar que todos los indicadores están calculados
        required = [ema_f, ema_t, "adx_14", "atr_14", "rsi_14"]
        if any(pd.isna(row.get(col)) for col in required):
            continue

        adx = row["adx_14"]
        if adx < config.adx_min:
            continue

        atr = row["atr_14"]
        close = row["close"]
        prev_close = prev["close"]

        # Tendencia en 15m
        bullish_trend = close > row[ema_t] and row[ema_f] > row[ema_t]
        bearish_trend = close < row[ema_t] and row[ema_f] < row[ema_t]

        # Filtro HTF: confirmar dirección con H4
        if config.htf_trend_enabled:
            htf_trend = int(row.get("htf_trend", 0))
            if bullish_trend and htf_trend < 0:
                continue
            if bearish_trend and htf_trend > 0:
                continue

        if bullish_trend:
            pullback_touch = prev_close < prev[ema_f] and close > row[ema_f]
            rsi_ok = row["rsi_14"] < config.rsi_overbought

            if pullback_touch and rsi_ok:
                sl = close - atr * config.atr_sl_mult
                tp = close + (close - sl) * config.rr_target
                signals.append(Signal(
                    symbol=df.attrs.get("symbol", "UNKNOWN"),
                    side=Side.LONG,
                    signal_type=SignalType.PULLBACK,
                    timestamp=ts,
                    entry_price=close,
                    stop_loss=sl,
                    take_profit=tp,
                ))
                signals_today[day_key] = signals_today.get(day_key, 0) + 1

        elif bearish_trend:
            pullback_touch = prev_close > prev[ema_f] and close < row[ema_f]
            rsi_ok = row["rsi_14"] > config.rsi_oversold

            if pullback_touch and rsi_ok:
                sl = close + atr * config.atr_sl_mult
                tp = close - (sl - close) * config.rr_target
                signals.append(Signal(
                    symbol=df.attrs.get("symbol", "UNKNOWN"),
                    side=Side.SHORT,
                    signal_type=SignalType.PULLBACK,
                    timestamp=ts,
                    entry_price=close,
                    stop_loss=sl,
                    take_profit=tp,
                ))
                signals_today[day_key] = signals_today.get(day_key, 0) + 1

    return signals
