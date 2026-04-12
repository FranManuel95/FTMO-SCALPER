# strategy/signal_engine.py — MTF v3: London + NY, EMA9/21 cross + pullback
# Estrategia multi-timeframe para EURUSD y GBPUSD.
# Genera señales en sesión London (07-17 UTC) y NY (13-20 UTC).
# Dos modos de entrada:
#   1. CROSSOVER: cruce EMA9/EMA21 en 5M (momentum agresivo)
#   2. PULLBACK : precio regresa a EMA21 después de cruce (entrada más conservadora)

import pandas as pd
from datetime import datetime, time
from dataclasses import dataclass, field
from enum import Enum

from core.indicators import ema, adx, rsi, atr, vwap_ema
from config.settings import (
    MTF_EMA_TREND, MTF_EMA_FAST, MTF_EMA_SLOW,
    MTF_EMA_ENTRY, MTF_EMA_CONFIRM,
    MTF_ADX_PERIOD, MTF_ADX_MIN, MTF_ADX_MAX,
    MTF_RSI_PERIOD, MTF_ATR_PERIOD,
    MTF_ATR_SL_MULT, MTF_RR_RATIO, MTF_ATR_MIN, MTF_TRAIL_MULT,
    LONDON_OPEN, LONDON_CLOSE, NY_OPEN, NY_CLOSE,
)


class Signal(Enum):
    BUY  = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class EntryMode(Enum):
    CROSSOVER = "CROSSOVER"   # Cruce EMA9/21 (señal rápida, más frecuente)
    PULLBACK  = "PULLBACK"    # Pullback a EMA21 tras tendencia establecida


@dataclass
class TradeSetup:
    signal:      Signal
    entry_price: float
    stop_loss:   float
    take_profit: float
    sl_pips:     float
    rr_ratio:    float
    reason:      str
    trail_mult:  float = field(default=MTF_TRAIL_MULT)
    entry_mode:  EntryMode = field(default=EntryMode.CROSSOVER)


_NONE = TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Sin señal")


class SignalEngine:
    """
    Motor de señales MTF para pares Forex (EURUSD, GBPUSD).

    Lógica de 3 capas:
      1H  → bias de tendencia (EMA200 + ADX)
      15M → confirmación de setup (EMA20/50 + RSI + VWAP)
      5M  → entrada (cruce EMA9/21 o pullback a EMA21)

    Mejoras v3 vs v2:
      - Soporte sesión NY (13-20 UTC) además de London
      - Modo PULLBACK: genera más señales en tendencias establecidas
      - RSI de entrada en 5M como filtro adicional de sobrecompra/venta
      - Refactorizado para usar core/indicators.py y config/settings.py
    """

    def __init__(self):
        self._df_1h:  pd.DataFrame | None = None
        self._df_15m: pd.DataFrame | None = None

    # ─────────────────────────────────────────────
    # SESIONES
    # ─────────────────────────────────────────────

    def is_valid_session(self) -> bool:
        """True si estamos dentro de London o NY."""
        now = datetime.utcnow().time()
        london = time(*LONDON_OPEN) <= now <= time(*LONDON_CLOSE)
        ny     = time(*NY_OPEN)     <= now <= time(*NY_CLOSE)
        return london or ny

    def _current_session(self) -> str:
        now = datetime.utcnow().time()
        if time(*NY_OPEN) <= now <= time(*NY_CLOSE):
            return "NY"
        return "LON"

    # ─────────────────────────────────────────────
    # ACTUALIZACIÓN DE TIMEFRAMES SUPERIORES
    # ─────────────────────────────────────────────

    def update_higher_timeframes(self, df_1h: pd.DataFrame,
                                  df_15m: pd.DataFrame) -> None:
        self._df_1h  = self._prepare_1h(df_1h)
        self._df_15m = self._prepare_15m(df_15m)

    def _prepare_1h(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df['close']
        df['ema200'] = ema(close, MTF_EMA_TREND)
        adx_df = adx(df, MTF_ADX_PERIOD)
        df = pd.concat([df, adx_df], axis=1)

        in_regime = (df['adx'] > MTF_ADX_MIN) & (df['adx'] < MTF_ADX_MAX)
        df['bias_bull'] = (close > df['ema200']) & in_regime & \
                          (df['plus_di'] > df['minus_di'])
        df['bias_bear'] = (close < df['ema200']) & in_regime & \
                          (df['minus_di'] > df['plus_di'])
        return df.dropna()

    def _prepare_15m(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df['close']
        df['ema20']  = ema(close, MTF_EMA_FAST)
        df['ema50']  = ema(close, MTF_EMA_SLOW)
        df['rsi']    = rsi(close, MTF_RSI_PERIOD)
        df['vwap']   = vwap_ema(close)
        df['setup_bull'] = (df['ema20'] > df['ema50']) & \
                           df['rsi'].between(45, 75) & \
                           (close > df['vwap'] * 0.9998)
        df['setup_bear'] = (df['ema20'] < df['ema50']) & \
                           df['rsi'].between(25, 55) & \
                           (close < df['vwap'] * 1.0002)
        return df.dropna()

    # ─────────────────────────────────────────────
    # ANÁLISIS PRINCIPAL
    # ─────────────────────────────────────────────

    def analyze(self, df_5m: pd.DataFrame) -> TradeSetup:
        if not self.is_valid_session():
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Fuera de sesión")
        if self._df_1h is None or self._df_15m is None:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Sin datos HTF")
        if len(df_5m) < 30:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0, "Pocas velas 5M")

        # ── Preparar 5M ──
        df = df_5m.copy()
        df['atr']  = atr(df, MTF_ATR_PERIOD)
        df['rsi']  = rsi(df['close'], MTF_RSI_PERIOD)
        close      = df['close']
        df['ema9'] = ema(close, MTF_EMA_ENTRY)
        df['ema21']= ema(close, MTF_EMA_CONFIRM)
        df = df.dropna()

        if len(df) < 3:
            return _NONE

        curr_atr = float(df['atr'].iloc[-1])
        if curr_atr < MTF_ATR_MIN:
            return TradeSetup(Signal.NONE, 0, 0, 0, 0, 0,
                              f"ATR bajo ({curr_atr:.5f} < {MTF_ATR_MIN})")

        # ── Contexto HTF ──
        ts      = df.index[-1]
        row_1h  = self._get_htf_row(self._df_1h, ts)
        row_15m = self._get_htf_row(self._df_15m, ts)
        if row_1h is None or row_15m is None:
            return _NONE

        # ── Calcular SL/TP ──
        entry     = float(df['close'].iloc[-1])
        sl_dist   = curr_atr * MTF_ATR_SL_MULT
        sl_pips   = sl_dist / 0.0001
        session   = self._current_session()

        # ── Intentar señal CROSSOVER ──
        cross_signal = self._check_crossover(df)
        if cross_signal != Signal.NONE:
            setup = self._build_setup(
                signal=cross_signal, entry=entry, sl_dist=sl_dist,
                sl_pips=sl_pips, row_1h=row_1h, row_15m=row_15m,
                mode=EntryMode.CROSSOVER, session=session, df=df
            )
            if setup is not None:
                return setup

        # ── Intentar señal PULLBACK ──
        pull_signal = self._check_pullback(df)
        if pull_signal != Signal.NONE:
            setup = self._build_setup(
                signal=pull_signal, entry=entry, sl_dist=sl_dist,
                sl_pips=sl_pips, row_1h=row_1h, row_15m=row_15m,
                mode=EntryMode.PULLBACK, session=session, df=df
            )
            if setup is not None:
                return setup

        return _NONE

    # ─────────────────────────────────────────────
    # DETECCIÓN DE ENTRADAS
    # ─────────────────────────────────────────────

    def _check_crossover(self, df: pd.DataFrame) -> Signal:
        """Cruce EMA9 sobre EMA21 (o debajo) en la última vela."""
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        if float(prev['ema9']) <= float(prev['ema21']) and \
           float(curr['ema9']) >  float(curr['ema21']):
            return Signal.BUY
        if float(prev['ema9']) >= float(prev['ema21']) and \
           float(curr['ema9']) <  float(curr['ema21']):
            return Signal.SELL
        return Signal.NONE

    def _check_pullback(self, df: pd.DataFrame) -> Signal:
        """
        Precio toca la EMA21 en tendencia establecida (EMA9 > EMA21 desde hace ≥3 velas).
        Esto genera entradas más frecuentes sin esperar cruces nuevos.
        """
        if len(df) < 5:
            return Signal.NONE
        curr  = df.iloc[-1]
        close = float(curr['close'])
        ema9  = float(curr['ema9'])
        ema21 = float(curr['ema21'])
        atr_v = float(curr['atr'])

        # Zona de pullback: precio dentro de ±0.5 ATR de EMA21
        near_ema21 = abs(close - ema21) < atr_v * 0.5

        # Tendencia alcista establecida (últimas 3 velas: EMA9 > EMA21)
        bull_trend = all(
            float(df.iloc[i]['ema9']) > float(df.iloc[i]['ema21'])
            for i in range(-4, -1)
        )
        # Tendencia bajista establecida
        bear_trend = all(
            float(df.iloc[i]['ema9']) < float(df.iloc[i]['ema21'])
            for i in range(-4, -1)
        )

        if bull_trend and near_ema21 and close > ema21:
            return Signal.BUY
        if bear_trend and near_ema21 and close < ema21:
            return Signal.SELL
        return Signal.NONE

    # ─────────────────────────────────────────────
    # VALIDACIÓN Y CONSTRUCCIÓN DEL SETUP
    # ─────────────────────────────────────────────

    def _build_setup(self, signal: Signal, entry: float,
                     sl_dist: float, sl_pips: float,
                     row_1h, row_15m,
                     mode: EntryMode, session: str,
                     df: pd.DataFrame) -> TradeSetup | None:
        """
        Valida el contexto HTF y construye el TradeSetup si es válido.
        Retorna None si las condiciones HTF no están alineadas.
        """
        curr_rsi = float(df['rsi'].iloc[-1])

        if signal == Signal.BUY:
            if not (row_1h['bias_bull'] and row_15m['setup_bull']):
                return None
            # Filtro adicional: RSI 5M no debe estar sobrecomprado
            if curr_rsi > 72:
                return None
            sl = entry - sl_dist
            tp = entry + sl_dist * MTF_RR_RATIO
        else:  # SELL
            if not (row_1h['bias_bear'] and row_15m['setup_bear']):
                return None
            # Filtro: RSI 5M no debe estar sobrevendido
            if curr_rsi < 28:
                return None
            sl = entry + sl_dist
            tp = entry - sl_dist * MTF_RR_RATIO

        reason = (
            f"{signal.value} [{mode.value}|{session}] "
            f"1H ADX={row_1h['adx']:.0f} | "
            f"15M RSI={row_15m['rsi']:.0f} | "
            f"5M RSI={curr_rsi:.0f}"
        )
        return TradeSetup(
            signal=signal, entry_price=entry,
            stop_loss=sl, take_profit=tp,
            sl_pips=sl_pips, rr_ratio=MTF_RR_RATIO,
            reason=reason, trail_mult=MTF_TRAIL_MULT,
            entry_mode=mode
        )

    # ─────────────────────────────────────────────
    # UTILIDADES
    # ─────────────────────────────────────────────

    def _get_htf_row(self, df_htf: pd.DataFrame, ts):
        """Obtiene la fila del HTF correspondiente al timestamp de la vela 5M."""
        idx = df_htf.index.searchsorted(ts) - 1
        if idx < 0 or idx >= len(df_htf):
            return None
        return df_htf.iloc[idx]
