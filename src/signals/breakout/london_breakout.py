from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.core.types import Side, Signal, SignalType
from src.features.session.asian_range import add_asian_range
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_htf_trend, add_weekly_regime


@dataclass
class LondonBreakoutConfig:
    adx_min: float = 22.0
    rr_target: float = 2.0
    breakout_buffer_atr: float = 0.2
    atr_sl_mult: float = 1.5
    asian_range_min_atr: float = 0.5   # rango mínimo (filtra días planos)
    asian_range_max_atr: float = 4.0   # rango máximo (filtra gaps/noticias)
    max_signals_per_day: int = 1
    tz_offset_hours: int = 2
    # Filtro de tendencia en timeframe superior
    htf_trend_enabled: bool = True
    htf_resample: str = "4h"
    htf_ema_fast: int = 50
    htf_ema_slow: int = 200
    # Filtro macro semanal
    weekly_regime_enabled: bool = False
    weekly_ema_period: int = 50

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


@dataclass
class SignalDiagnostic:
    timestamp: datetime
    side: str
    entry: float
    sl: float
    tp: float
    asian_range: float
    atr: float
    adx: float
    htf_trend: int
    rr: float
    filter_rejected: str = ""  # razón de rechazo si no generó señal


def generate_london_breakout_signals(
    df: pd.DataFrame,
    config: LondonBreakoutConfig | None = None,
    return_diagnostics: bool = False,
) -> list[Signal] | tuple[list[Signal], list[dict]]:
    """
    Estrategia de breakout del rango asiático en apertura London.

    Filtros activos:
    - ADX mínimo en 15m
    - Rango asiático entre 0.5x y 4x ATR
    - Tendencia H4: solo long en alcista, solo short en bajista
    - Máximo 1 señal por día
    - SL = entrada ± ATR * sl_mult (no el rango completo)
    """
    if config is None:
        config = LondonBreakoutConfig()

    df = df.copy()
    df = add_asian_range(df, session_start_h=config.asian_start_h, session_end_h=config.asian_end_h)
    df = add_atr(df, 14)
    df = add_adx(df, 14)

    if config.htf_trend_enabled:
        df = add_htf_trend(df, htf_resample=config.htf_resample,
                           ema_fast=config.htf_ema_fast, ema_slow=config.htf_ema_slow)

    if config.weekly_regime_enabled:
        df = add_weekly_regime(df, ema_period=config.weekly_ema_period)

    signals: list[Signal] = []
    diagnostics: list[dict] = []
    signals_today: dict[str, int] = {}

    ls_h = config.london_start_h
    le_h = config.london_end_h

    for i in range(1, len(df)):
        row = df.iloc[i]
        ts: datetime = row.name.to_pydatetime()
        hour = ts.hour
        day_key = ts.strftime("%Y-%m-%d")

        in_london = (hour >= ls_h and hour < le_h) if ls_h < le_h else (hour >= ls_h or hour < le_h)
        if not in_london:
            continue

        atr = row.get("atr_14")
        asian_high = row.get("asian_high")
        asian_low = row.get("asian_low")
        asian_range = row.get("asian_range")
        adx = row.get("adx_14")
        htf_trend = int(row.get("htf_trend", 0)) if config.htf_trend_enabled else 0
        weekly_regime = row.get("weekly_regime", 0) if config.weekly_regime_enabled else 0
        close = row["close"]

        if any(pd.isna(v) for v in [atr, asian_high, asian_low, asian_range, adx]):
            continue

        # --- Filtros ---
        if signals_today.get(day_key, 0) >= config.max_signals_per_day:
            if return_diagnostics:
                diagnostics.append({"ts": ts, "reason": "max_signals_day", "close": close})
            continue

        if adx < config.adx_min:
            if return_diagnostics:
                diagnostics.append({"ts": ts, "reason": f"adx_low={adx:.1f}", "close": close})
            continue

        if asian_range < atr * config.asian_range_min_atr:
            if return_diagnostics:
                diagnostics.append({"ts": ts, "reason": f"range_too_small={asian_range:.2f}", "close": close})
            continue

        if asian_range > atr * config.asian_range_max_atr:
            if return_diagnostics:
                diagnostics.append({"ts": ts, "reason": f"range_too_large={asian_range:.2f}", "close": close})
            continue

        buffer = config.breakout_buffer_atr * atr
        is_long_break = close > asian_high + buffer
        is_short_break = close < asian_low - buffer

        if not is_long_break and not is_short_break:
            continue

        # Filtro tendencia HTF
        if config.htf_trend_enabled:
            if is_long_break and htf_trend < 0:
                if return_diagnostics:
                    diagnostics.append({"ts": ts, "reason": "htf_contra_long", "close": close, "htf_trend": htf_trend})
                continue
            if is_short_break and htf_trend > 0:
                if return_diagnostics:
                    diagnostics.append({"ts": ts, "reason": "htf_contra_short", "close": close, "htf_trend": htf_trend})
                continue

        # Filtro régimen semanal: solo operar en dirección del macro trend
        if config.weekly_regime_enabled and not pd.isna(weekly_regime):
            if is_long_break and weekly_regime < 0:
                continue
            if is_short_break and weekly_regime > 0:
                continue

        if is_long_break:
            sl = close - atr * config.atr_sl_mult
            risk = close - sl
            tp = close + risk * config.rr_target
            side = Side.LONG
        else:
            sl = close + atr * config.atr_sl_mult
            risk = sl - close
            tp = close - risk * config.rr_target
            side = Side.SHORT

        signals.append(Signal(
            symbol=df.attrs.get("symbol", "UNKNOWN"),
            side=side,
            signal_type=SignalType.BREAKOUT,
            timestamp=ts,
            entry_price=close,
            stop_loss=sl,
            take_profit=tp,
        ))

        if return_diagnostics:
            diagnostics.append({
                "ts": ts, "side": side.value, "entry": round(close, 3),
                "sl": round(sl, 3), "tp": round(tp, 3),
                "asian_range": round(asian_range, 3), "atr": round(atr, 3),
                "adx": round(adx, 1), "htf_trend": htf_trend,
                "rr": round(risk * config.rr_target / risk, 2),
                "reason": "SIGNAL",
            })

        signals_today[day_key] = signals_today.get(day_key, 0) + 1

    if return_diagnostics:
        return signals, diagnostics
    return signals
