from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.session.asian_range import add_asian_range
from src.features.technical.indicators import add_adx, add_atr


@dataclass
class LondonBreakoutConfig:
    adx_min: float = 22.0
    rr_target: float = 2.0
    breakout_buffer_atr: float = 0.2   # buffer encima/debajo del rango para confirmar breakout
    atr_sl_mult: float = 1.5           # SL = entrada ± ATR * atr_sl_mult (NO el rango completo)
    asian_range_min_atr: float = 0.5   # rango asiático mínimo como múltiplo del ATR (filtra dias planos)
    asian_range_max_atr: float = 4.0   # rango asiático máximo (filtra dias con gap/noticias)
    max_signals_per_day: int = 1
    # Offset timezone del broker respecto a UTC (2 = UTC+2 EET, 3 = UTC+3 EEST)
    tz_offset_hours: int = 2

    @property
    def asian_start_h(self) -> int:
        return (0 + self.tz_offset_hours) % 24

    @property
    def asian_end_h(self) -> int:
        return (7 + self.tz_offset_hours) % 24

    @property
    def london_start_h(self) -> int:
        return (7 + self.tz_offset_hours) % 24

    @property
    def london_end_h(self) -> int:
        return (12 + self.tz_offset_hours) % 24


def generate_london_breakout_signals(
    df: pd.DataFrame,
    config: LondonBreakoutConfig | None = None,
) -> list[Signal]:
    """
    Estrategia de breakout del rango asiático en apertura London.

    Lógica:
    1. Rango asiático (broker time) define el contexto de compresión
    2. En ventana London, detectar cierre fuera del rango + buffer
    3. Confirmar con ADX > mínimo
    4. Filtrar rangos asiáticos anormalmente pequeños o grandes
    5. SL = entrada ± ATR*mult (no el rango completo — más RR realista)
    """
    if config is None:
        config = LondonBreakoutConfig()

    df = df.copy()
    df = add_asian_range(df, session_start_h=config.asian_start_h, session_end_h=config.asian_end_h)
    df = add_atr(df, 14)
    df = add_adx(df, 14)

    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    ls_h = config.london_start_h
    le_h = config.london_end_h

    for i in range(1, len(df)):
        row = df.iloc[i]
        ts: datetime = row.name.to_pydatetime()
        hour = ts.hour
        day_key = ts.strftime("%Y-%m-%d")

        # Ventana London en hora del broker
        in_london = (hour >= ls_h and hour < le_h) if ls_h < le_h else (hour >= ls_h or hour < le_h)
        if not in_london:
            continue

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        atr = row.get("atr_14")
        asian_high = row.get("asian_high")
        asian_low = row.get("asian_low")
        asian_range = row.get("asian_range")
        adx = row.get("adx_14")

        if any(pd.isna(v) for v in [atr, asian_high, asian_low, asian_range, adx]):
            continue

        # Filtro ADX: tendencia mínima
        if adx < config.adx_min:
            continue

        # Filtro rango asiático: ni demasiado pequeño ni demasiado grande
        if asian_range < atr * config.asian_range_min_atr:
            continue
        if asian_range > atr * config.asian_range_max_atr:
            continue

        buffer = config.breakout_buffer_atr * atr
        close = row["close"]

        if close > asian_high + buffer:
            # SL basado en ATR desde la entrada, no en el rango completo
            sl = close - atr * config.atr_sl_mult
            risk = close - sl
            tp = close + risk * config.rr_target
            signals.append(Signal(
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                side=Side.LONG,
                signal_type=SignalType.BREAKOUT,
                timestamp=ts,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            ))
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

        elif close < asian_low - buffer:
            sl = close + atr * config.atr_sl_mult
            risk = sl - close
            tp = close - risk * config.rr_target
            signals.append(Signal(
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                side=Side.SHORT,
                signal_type=SignalType.BREAKOUT,
                timestamp=ts,
                entry_price=close,
                stop_loss=sl,
                take_profit=tp,
            ))
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

    return signals
