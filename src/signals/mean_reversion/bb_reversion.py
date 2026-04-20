from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.technical.indicators import add_adx, add_atr, add_bollinger, add_rsi
from src.features.trend.htf_filter import add_htf_adx


@dataclass
class BBReversionConfig:
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    adx_max: float = 25.0      # solo operar en rango (ADX bajo)
    daily_adx_max: float = 0.0  # 0 = desactivado; >0 filtra tendencias macro (ej: 25)
    rr_target: float = 1.5
    atr_sl_mult: float = 1.0
    max_signals_per_day: int = 2
    session_filter: bool = True
    tz_offset_hours: int = 2


def generate_bb_reversion_signals(
    df: pd.DataFrame,
    config: BBReversionConfig | None = None,
) -> list[Signal]:
    """
    Mean reversion sobre Bollinger Bands:
    - LONG  cuando close < BB inferior Y RSI < oversold Y ADX < adx_max
    - SHORT cuando close > BB superior Y RSI > overbought Y ADX < adx_max
    SL = entrada ± ATR * sl_mult  /  TP = entrada ± (SL_dist * rr_target)
    """
    if config is None:
        config = BBReversionConfig()

    df = df.copy()
    df = add_bollinger(df, config.bb_period, config.bb_std)
    df = add_adx(df, 14)
    df = add_atr(df, 14)
    df = add_rsi(df, config.rsi_period)
    if config.daily_adx_max > 0:
        df = add_htf_adx(df, htf_resample="1D", adx_length=14)

    timestamps = df.index.to_pydatetime()
    hours      = df.index.hour
    close_arr  = df["close"].values
    bb_upper   = df["bb_upper"].values
    bb_lower   = df["bb_lower"].values
    bb_mid     = df["bb_mid"].values
    adx_arr    = df["adx_14"].values
    atr_arr    = df["atr_14"].values
    rsi_arr    = df[f"rsi_{config.rsi_period}"].values
    daily_adx  = df["htf_adx_14"].values if config.daily_adx_max > 0 else None

    s_start = (7  + config.tz_offset_hours) % 24
    s_end   = (21 + config.tz_offset_hours) % 24
    symbol  = df.attrs.get("symbol", "UNKNOWN")

    signals: list[Signal] = []
    signals_today: dict[str, int] = {}

    for i in range(2, len(df)):
        hour = hours[i]

        if config.session_filter:
            if s_start < s_end:
                if not (s_start <= hour < s_end):
                    continue
            else:
                if not (hour >= s_start or hour < s_end):
                    continue

        ts      = timestamps[i]
        day_key = ts.strftime("%Y-%m-%d")

        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            continue

        if np.isnan(adx_arr[i]) or np.isnan(atr_arr[i]) or np.isnan(rsi_arr[i]):
            continue
        if np.isnan(bb_upper[i]) or np.isnan(bb_lower[i]):
            continue

        # Solo en mercado lateral (H1)
        if adx_arr[i] >= config.adx_max:
            continue

        # Filtro macro: si ADX diario > umbral, el macro está en tendencia → skip
        if daily_adx is not None and not np.isnan(daily_adx[i]) and daily_adx[i] >= config.daily_adx_max:
            continue

        close = close_arr[i]
        atr   = atr_arr[i]
        rsi   = rsi_arr[i]

        mid  = bb_mid[i]
        dist_to_mid = abs(close - mid)

        # LONG: cierre bajo BB inferior + RSI oversold + distancia mínima a mid (evita señales débiles)
        if close < bb_lower[i] and rsi < config.rsi_oversold and dist_to_mid > atr * 0.5:
            sl   = close - atr * config.atr_sl_mult
            risk = close - sl
            # TP en BB midline (objetivo natural de mean reversion)
            tp_mid  = mid
            rr_real = (tp_mid - close) / risk if risk > 0 else 0
            # Solo tomar si RR hacia midline es al menos rr_target
            if rr_real < config.rr_target:
                continue
            signals.append(Signal(
                symbol=symbol, side=Side.LONG,
                signal_type=SignalType.MEAN_REVERSION,
                timestamp=ts, entry_price=close,
                stop_loss=sl, take_profit=tp_mid,
            ))
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

        # SHORT: cierre sobre BB superior + RSI overbought
        elif close > bb_upper[i] and rsi > config.rsi_overbought and dist_to_mid > atr * 0.5:
            sl   = close + atr * config.atr_sl_mult
            risk = sl - close
            tp_mid  = mid
            rr_real = (close - tp_mid) / risk if risk > 0 else 0
            if rr_real < config.rr_target:
                continue
            signals.append(Signal(
                symbol=symbol, side=Side.SHORT,
                signal_type=SignalType.MEAN_REVERSION,
                timestamp=ts, entry_price=close,
                stop_loss=sl, take_profit=tp_mid,
            ))
            signals_today[day_key] = signals_today.get(day_key, 0) + 1

    return signals
