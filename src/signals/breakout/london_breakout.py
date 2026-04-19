from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.session.asian_range import add_asian_range
from src.features.technical.indicators import add_adx, add_atr


@dataclass
class LondonBreakoutConfig:
    adx_min: float = 22.0
    atr_min_mult: float = 1.0
    rr_target: float = 2.0
    london_start_utc: str = "07:00"
    london_end_utc: str = "12:00"
    breakout_buffer_atr: float = 0.1
    max_signals_per_day: int = 1


def generate_london_breakout_signals(
    df: pd.DataFrame,
    config: LondonBreakoutConfig | None = None,
) -> list[Signal]:
    """
    Estrategia de breakout del rango asiático en apertura London.

    Lógica:
    1. Identificar rango asiático (00:00-07:00 UTC)
    2. En ventana London, detectar cierre fuera del rango
    3. Confirmar con ADX H1 > mínimo
    4. Generar señal con SL en límite opuesto del rango
    """
    if config is None:
        config = LondonBreakoutConfig()

    df = df.copy()
    df = add_asian_range(df)
    df = add_atr(df, 14)
    df = add_adx(df, 14)

    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    london_start_h = int(config.london_start_utc.split(":")[0])
    london_end_h = int(config.london_end_utc.split(":")[0])

    for i in range(1, len(df)):
        row = df.iloc[i]
        ts: datetime = row.name.to_pydatetime()
        hour = ts.hour
        day_key = ts.strftime("%Y-%m-%d")

        if not (london_start_h <= hour < london_end_h):
            continue

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        if pd.isna(row.get("asian_high")) or pd.isna(row.get("adx_14")):
            continue

        atr = row["atr_14"]
        if pd.isna(atr) or atr < config.atr_min_mult * 0.0001:
            continue

        adx = row["adx_14"]
        if adx < config.adx_min:
            continue

        buffer = config.breakout_buffer_atr * atr
        close = row["close"]
        asian_high = row["asian_high"]
        asian_low = row["asian_low"]

        if close > asian_high + buffer:
            sl = asian_low
            risk = close - sl
            tp = close + risk * config.rr_target
            signal = Signal(
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                side=Side.LONG,
                signal_type=SignalType.BREAKOUT,
                timestamp=ts,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            )
            signals.append(signal)
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

        elif close < asian_low - buffer:
            sl = asian_high
            risk = sl - close
            tp = close - risk * config.rr_target
            signal = Signal(
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                side=Side.SHORT,
                signal_type=SignalType.BREAKOUT,
                timestamp=ts,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            )
            signals.append(signal)
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

    return signals
