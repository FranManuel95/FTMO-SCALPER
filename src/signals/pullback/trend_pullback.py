from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr, add_ema, add_rsi


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


def generate_pullback_signals(
    df: pd.DataFrame,
    config: TrendPullbackConfig | None = None,
) -> list[Signal]:
    """
    Pullback en tendencia: entra cuando el precio retrocede hacia EMA en tendencia confirmada.

    Lógica:
    1. Tendencia definida por precio > EMA50 (alcista) o < EMA50 (bajista)
    2. ADX > mínimo para confirmar tendencia
    3. Pullback: EMA20 retrocede hacia EMA50
    4. RSI < 45 en pullback alcista (sobreventa relativa)
    5. Entrada cuando precio rebota de EMA20
    """
    if config is None:
        config = TrendPullbackConfig()

    df = df.copy()
    df = add_ema(df, [config.ema_fast, config.ema_trend])
    df = add_adx(df, 14)
    df = add_atr(df, 14)
    df = add_rsi(df, 14)

    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    ema_f = f"ema_{config.ema_fast}"
    ema_t = f"ema_{config.ema_trend}"

    for i in range(2, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        ts: datetime = row.name.to_pydatetime()
        day_key = ts.strftime("%Y-%m-%d")

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        for col in [ema_f, ema_t, "adx_14", "atr_14", "rsi_14"]:
            if pd.isna(row.get(col)):
                continue

        adx = row["adx_14"]
        if adx < config.adx_min:
            continue

        atr = row["atr_14"]
        close = row["close"]
        prev_close = prev["close"]

        bullish_trend = close > row[ema_t] and row[ema_f] > row[ema_t]
        bearish_trend = close < row[ema_t] and row[ema_f] < row[ema_t]

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
