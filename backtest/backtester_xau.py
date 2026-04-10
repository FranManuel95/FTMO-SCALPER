# backtest/backtester_xau.py
# XAUUSD Opening Range Breakout v5
# - Datos base: M1
# - Construye M5 y H1 desde M1
# - ORB sobre M5
# - Filtro H1 causal (sin lookahead)
# - Confirmación por cierre M5 y entrada en la SIGUIENTE apertura M5
# - Ejecución intrabar sobre M1
# - Gestión FTMO-friendly
# - Diagnóstico interno
# - Selector de dirección: BOTH / BUY_ONLY / SELL_ONLY
# - Filtro opcional por fechas
# - Filtro de régimen H1 reforzado para intentar captar solo el contexto válido

import os
import numpy as np
import pandas as pd

from backtest.backtester import BacktestResult


class XAUBacktester:
    DATA_PATH_M1 = "backtest/data/XAUUSD_M1.csv"
    NEWS_PATH = "backtest/data/us_macro_events.csv"  # opcional

    # =========================================================
    # Timezone
    # =========================================================
    INPUT_TIMEZONE = None
    TARGET_TIMEZONE = None

    # =========================================================
    # Ventanas horarias
    # =========================================================
    ORB_START_HOUR = 7
    ORB_END_HOUR = 9
    TRADE_START_HOUR = 9
    TRADE_END_HOUR = 16

    # =========================================================
    # Filtros H1
    # =========================================================
    H1_EMA_FAST = 20
    H1_EMA_SLOW = 50
    ADX_PERIOD = 14
    ADX_MIN = 18
    ADX_MAX = 60

    # =========================================================
    # Filtro de régimen H1
    # =========================================================
    USE_REGIME_FILTER = True
    REGIME_ADX_MIN = 22
    H1_SLOPE_LOOKBACK = 2
    MIN_H1_EMA_SPREAD_ATR = 0.15

    # =========================================================
    # Filtros / entrada M5
    # =========================================================
    ATR_PERIOD = 14
    ATR_MIN = 1.0
    BREAKOUT_BUFFER_ATR = 0.03
    BODY_PCT_MIN = 0.25
    MIN_ORB_ATR = 0.20
    MAX_ORB_ATR = 8.00

    # =========================================================
    # Gestión
    # =========================================================
    ATR_SL_MULT = 1.10
    RR_RATIO = 1.50
    MAX_TRADES_DAY = 1
    MAX_HOLD_M5_BARS = 24
    BREAKEVEN_TRIGGER_R = 1.0
    NEWS_BLACKOUT_MIN = 60

    # BOTH | BUY_ONLY | SELL_ONLY
    TRADE_MODE = "SELL_ONLY"

    # Coste fijo opcional por trade (round turn), en dinero
    TRADE_COST_FIXED = 0.0

    # =========================================================
    # Salida por estancamiento
    # =========================================================
    USE_STAGNATION_EXIT = False
    STAGNATION_CHECK_M5_BARS = 6
    STAGNATION_MIN_PROGRESS_R = 0.30

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade: float = 0.005,
        rr_ratio: float = 1.5,
        trade_mode: str = None,
        start_date=None,
        end_date=None,
    ):
        self.initial_balance = float(initial_balance)
        self.risk_per_trade = float(risk_per_trade)
        self.rr_ratio = float(rr_ratio)
        self.trade_mode = self._normalize_trade_mode(trade_mode or self.TRADE_MODE)
        self.start_date = self._normalize_single_ts(start_date)
        self.end_date = self._normalize_single_ts(end_date)
        self.last_diagnostics = {}

    # =========================================================
    # Helpers generales
    # =========================================================
    def _normalize_trade_mode(self, mode: str) -> str:
        mode = str(mode).upper().strip()
        valid = {"BOTH", "BUY_ONLY", "SELL_ONLY"}
        if mode not in valid:
            raise ValueError(
                f"trade_mode inválido: {mode}. Usa uno de: {sorted(valid)}"
            )
        return mode

    def _is_buy_allowed(self) -> bool:
        return self.trade_mode in {"BOTH", "BUY_ONLY"}

    def _is_sell_allowed(self) -> bool:
        return self.trade_mode in {"BOTH", "SELL_ONLY"}

    def _normalize_single_ts(self, ts):
        if ts is None:
            return None
        ts = pd.Timestamp(ts)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        return ts

    # =========================================================
    # Helpers datetime / timezone
    # =========================================================
    def _normalize_datetime_index(self, idx: pd.Index) -> pd.DatetimeIndex:
        idx = pd.to_datetime(idx, errors="coerce")
        idx = pd.DatetimeIndex(idx)
        idx = idx[~idx.isna()]

        if len(idx) == 0:
            return idx

        if idx.tz is None:
            if self.INPUT_TIMEZONE:
                idx = idx.tz_localize(
                    self.INPUT_TIMEZONE,
                    ambiguous="infer",
                    nonexistent="shift_forward",
                )
                if self.TARGET_TIMEZONE:
                    idx = idx.tz_convert(self.TARGET_TIMEZONE)
                idx = idx.tz_localize(None)
            return idx

        if self.TARGET_TIMEZONE:
            idx = idx.tz_convert(self.TARGET_TIMEZONE)

        return idx.tz_localize(None)

    def _normalize_datetime_series(self, s: pd.Series) -> pd.Series:
        s = pd.to_datetime(s, errors="coerce")

        if s.empty:
            return s

        try:
            if getattr(s.dt, "tz", None) is None:
                if self.INPUT_TIMEZONE:
                    s = s.dt.tz_localize(
                        self.INPUT_TIMEZONE,
                        ambiguous="infer",
                        nonexistent="shift_forward",
                    )
                    if self.TARGET_TIMEZONE:
                        s = s.dt.tz_convert(self.TARGET_TIMEZONE)
                    s = s.dt.tz_localize(None)
                return s

            if self.TARGET_TIMEZONE:
                s = s.dt.tz_convert(self.TARGET_TIMEZONE)

            return s.dt.tz_localize(None)
        except Exception:
            return pd.to_datetime(s, errors="coerce")

    # =========================================================
    # Carga de datos
    # =========================================================
    def _read_ohlc_csv(self, path: str) -> pd.DataFrame:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No se encontró el archivo: {path}\n"
                "Necesitas backtest/data/XAUUSD_M1.csv"
            )

        df = pd.read_csv(path, index_col=0)
        df.columns = [c.lower() for c in df.columns]

        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Faltan columnas OHLC en {path}: {missing}")

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["open", "high", "low", "close"]).copy()

        df.index = self._normalize_datetime_index(df.index)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]

        if self.start_date is not None:
            df = df[df.index >= self.start_date]

        if self.end_date is not None:
            df = df[df.index <= self.end_date]

        if df.empty:
            raise ValueError(
                f"No hay datos en el rango solicitado: start_date={self.start_date}, end_date={self.end_date}"
            )

        return df

    def _resample_ohlc(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }

        if "volume" in df.columns:
            agg["volume"] = "sum"
        if "vol" in df.columns:
            agg["vol"] = "sum"

        out = df.resample(rule, label="left", closed="left").agg(agg)
        out = out.dropna(subset=["open", "high", "low", "close"])
        return out

    def load_data(self):
        df_m1 = self._read_ohlc_csv(self.DATA_PATH_M1)
        df_m5 = self._resample_ohlc(df_m1, "5min")
        df_h1 = self._resample_ohlc(df_m1, "1h")

        print(
            f"XAUUSD M1: {len(df_m1)} | M5: {len(df_m5)} | "
            f"H1: {len(df_h1)} | Precio: {df_m1['close'].iloc[-1]:.2f} | "
            f"Mode: {self.trade_mode} | "
            f"Rango: {df_m1.index[0]} -> {df_m1.index[-1]}"
        )

        return df_m1, df_m5, df_h1

    # =========================================================
    # Indicadores
    # =========================================================
    def _wilder_rma(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(alpha=1 / period, adjust=False).mean()

    def _atr_series(self, df: pd.DataFrame, period: int) -> pd.Series:
        hl = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        return self._wilder_rma(tr, period)

    def _add_atr(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        period = period or self.ATR_PERIOD
        df = df.copy()
        df["atr"] = self._atr_series(df, period)
        return df

    def _add_adx(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        period = period or self.ADX_PERIOD
        df = df.copy()

        high = df["high"]
        low = df["low"]
        close = df["close"]

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=df.index,
            dtype=float,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=df.index,
            dtype=float,
        )

        hl = high - low
        hcp = (high - close.shift()).abs()
        lcp = (low - close.shift()).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)

        atr = self._wilder_rma(tr, period)
        plus_di = 100.0 * self._wilder_rma(plus_dm, period) / atr.replace(0, np.nan)
        minus_di = 100.0 * self._wilder_rma(minus_dm, period) / atr.replace(0, np.nan)

        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = self._wilder_rma(dx.fillna(0.0), period)

        df["plus_di"] = plus_di
        df["minus_di"] = minus_di
        df["adx"] = adx
        return df

    # =========================================================
    # Noticias opcionales
    # =========================================================
    def _load_news_events(self) -> pd.DatetimeIndex:
        if not os.path.exists(self.NEWS_PATH):
            return pd.DatetimeIndex([])

        try:
            df = pd.read_csv(self.NEWS_PATH)
        except Exception:
            return pd.DatetimeIndex([])

        if df.empty:
            return pd.DatetimeIndex([])

        dt_col = None
        for candidate in ["datetime", "timestamp", "time", "date"]:
            if candidate in df.columns:
                dt_col = candidate
                break

        if dt_col is None:
            return pd.DatetimeIndex([])

        if "impact" in df.columns:
            impact = df["impact"].astype(str).str.lower().str.strip()
            keep = impact.isin({"high", "medium", "medium-high", "medium high", "3", "2"})
            if keep.any():
                df = df[keep]

        events = self._normalize_datetime_series(df[dt_col]).dropna()
        if len(events) == 0:
            return pd.DatetimeIndex([])

        if self.start_date is not None:
            events = events[events >= self.start_date]
        if self.end_date is not None:
            events = events[events <= self.end_date]

        return pd.DatetimeIndex(events.sort_values().unique())

    def _in_news_blackout(self, ts: pd.Timestamp, events: pd.DatetimeIndex) -> bool:
        if len(events) == 0:
            return False

        ts = pd.Timestamp(ts)
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)

        blackout = pd.Timedelta(minutes=self.NEWS_BLACKOUT_MIN)
        pos = events.searchsorted(ts)

        if pos < len(events) and abs(events[pos] - ts) <= blackout:
            return True
        if pos > 0 and abs(events[pos - 1] - ts) <= blackout:
            return True

        return False

    # =========================================================
    # Preparación de marcos
    # =========================================================
    def _prepare_frames(self):
        df_m1, df_m5, df_h1 = self.load_data()

        df_m5 = self._add_atr(df_m5)
        df_m5["body"] = (df_m5["close"] - df_m5["open"]).abs()
        df_m5["range"] = (df_m5["high"] - df_m5["low"]).replace(0, np.nan)
        df_m5["body_pct"] = (df_m5["body"] / df_m5["range"]).fillna(0.0)

        df_h1 = self._add_atr(df_h1)
        df_h1["ema_fast"] = df_h1["close"].ewm(span=self.H1_EMA_FAST, adjust=False).mean()
        df_h1["ema_slow"] = df_h1["close"].ewm(span=self.H1_EMA_SLOW, adjust=False).mean()
        df_h1 = self._add_adx(df_h1)

        df_h1["ema_fast_slope_n"] = (
            df_h1["ema_fast"] - df_h1["ema_fast"].shift(self.H1_SLOPE_LOOKBACK)
        )
        df_h1["ema_spread_bull_atr"] = (
            (df_h1["ema_fast"] - df_h1["ema_slow"]) / df_h1["atr"].replace(0, np.nan)
        )
        df_h1["ema_spread_bear_atr"] = (
            (df_h1["ema_slow"] - df_h1["ema_fast"]) / df_h1["atr"].replace(0, np.nan)
        )

        h1_feats = df_h1[
            [
                "ema_fast",
                "ema_slow",
                "adx",
                "atr",
                "ema_fast_slope_n",
                "ema_spread_bull_atr",
                "ema_spread_bear_atr",
            ]
        ].shift(1)

        df_m5["h1_ema_fast"] = h1_feats["ema_fast"].reindex(df_m5.index, method="ffill")
        df_m5["h1_ema_slow"] = h1_feats["ema_slow"].reindex(df_m5.index, method="ffill")
        df_m5["h1_adx"] = h1_feats["adx"].reindex(df_m5.index, method="ffill")
        df_m5["h1_atr"] = h1_feats["atr"].reindex(df_m5.index, method="ffill")
        df_m5["h1_ema_fast_slope_n"] = h1_feats["ema_fast_slope_n"].reindex(df_m5.index, method="ffill")
        df_m5["h1_ema_spread_bull_atr"] = h1_feats["ema_spread_bull_atr"].reindex(df_m5.index, method="ffill")
        df_m5["h1_ema_spread_bear_atr"] = h1_feats["ema_spread_bear_atr"].reindex(df_m5.index, method="ffill")

        df_m5["date"] = df_m5.index.date
        df_m5["weekday"] = df_m5.index.weekday
        df_m5["month"] = df_m5.index.month
        df_m5["day"] = df_m5.index.day
        df_m5["hour"] = df_m5.index.hour

        needed = [
            "atr",
            "body_pct",
            "h1_ema_fast",
            "h1_ema_slow",
            "h1_adx",
            "h1_atr",
            "h1_ema_fast_slope_n",
            "h1_ema_spread_bull_atr",
            "h1_ema_spread_bear_atr",
        ]
        df_m5 = df_m5.dropna(subset=needed).copy()

        return df_m1, df_m5

    # =========================================================
    # Simulación intrabar
    # =========================================================
    def _simulate_trade_m1(
        self,
        df_m1: pd.DataFrame,
        signal_time: pd.Timestamp,
        session_end_time: pd.Timestamp,
        signal_side: str,
        entry: float,
        sl: float,
        tp: float,
        risk_distance: float,
    ):
        max_hold = pd.Timedelta(minutes=5 * self.MAX_HOLD_M5_BARS)
        end_time = min(signal_time + max_hold, session_end_time)

        future = df_m1[(df_m1.index >= signal_time) & (df_m1.index <= end_time)].copy()
        if future.empty:
            return signal_time, entry, "timeout", False, 0.0

        stop = sl
        be_armed = False
        best_r = 0.0

        stagnation_check_time = signal_time + pd.Timedelta(
            minutes=5 * self.STAGNATION_CHECK_M5_BARS
        )

        if signal_side == "BUY":
            be_trigger = entry + risk_distance * self.BREAKEVEN_TRIGGER_R
        else:
            be_trigger = entry - risk_distance * self.BREAKEVEN_TRIGGER_R

        for ts, bar in future.iterrows():
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])

            if signal_side == "BUY":
                current_best_r = (high - entry) / risk_distance
            else:
                current_best_r = (entry - low) / risk_distance
            best_r = max(best_r, current_best_r)

            if signal_side == "BUY":
                if low <= stop:
                    return ts, stop, "breakeven" if stop >= entry else "sl", be_armed, best_r
                if high >= tp:
                    return ts, tp, "tp", be_armed, best_r
                if (not be_armed) and high >= be_trigger:
                    stop = entry
                    be_armed = True
            else:
                if high >= stop:
                    return ts, stop, "breakeven" if stop <= entry else "sl", be_armed, best_r
                if low <= tp:
                    return ts, tp, "tp", be_armed, best_r
                if (not be_armed) and low <= be_trigger:
                    stop = entry
                    be_armed = True

            if (
                self.USE_STAGNATION_EXIT
                and ts >= stagnation_check_time
                and best_r < self.STAGNATION_MIN_PROGRESS_R
                and not be_armed
            ):
                return ts, close, "stagnation", be_armed, best_r

        last_ts = future.index[-1]
        last_close = float(future.iloc[-1]["close"])
        return last_ts, last_close, "timeout", be_armed, best_r

    # =========================================================
    # Equidad diaria
    # =========================================================
    def _build_daily_equity_curve(self, trades, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.Series:
        if start_ts is None or end_ts is None:
            return pd.Series(dtype=float)

        start_day = pd.Timestamp(start_ts).normalize()
        end_day = pd.Timestamp(end_ts).normalize()

        days = pd.date_range(start=start_day, end=end_day, freq="D")
        daily_eq = pd.Series(self.initial_balance, index=days, dtype=float)

        if not trades:
            return daily_eq[daily_eq.index.weekday < 5]

        by_day = {}
        for t in trades:
            exit_day = pd.Timestamp(t["exit_time"]).normalize()
            by_day[exit_day] = t["balance_after"]

        by_day = pd.Series(by_day).sort_index()
        daily_eq.update(by_day)
        daily_eq = daily_eq.ffill()
        daily_eq = daily_eq[daily_eq.index.weekday < 5]
        return daily_eq

    # =========================================================
    # Backtest
    # =========================================================
    def run(self) -> BacktestResult:
        df_m1, df_m5 = self._prepare_frames()
        news_events = self._load_news_events()

        balance = self.initial_balance
        equity_curve = [balance]
        trades = []

        exit_reason_counter = {
            "tp": 0,
            "sl": 0,
            "breakeven": 0,
            "timeout": 0,
            "stagnation": 0,
        }

        side_counter = {
            "BUY": 0,
            "SELL": 0,
        }

        be_activated_count = 0

        grouped = df_m5.groupby("date")

        for _, day_df in grouped:
            if day_df.empty:
                continue

            ts0 = day_df.index[0]

            if int(day_df["weekday"].iloc[0]) >= 5:
                continue

            if (ts0.month == 12 and ts0.day >= 20) or (ts0.month == 1 and ts0.day <= 3):
                continue

            orb = day_df[
                (day_df.index.hour >= self.ORB_START_HOUR)
                & (day_df.index.hour < self.ORB_END_HOUR)
            ].copy()

            session = day_df[
                (day_df.index.hour >= self.TRADE_START_HOUR)
                & (day_df.index.hour < self.TRADE_END_HOUR)
            ].copy()

            if orb.empty or session.empty:
                continue

            orb_high = float(orb["high"].max())
            orb_low = float(orb["low"].min())
            orb_range = orb_high - orb_low

            atr_ref = float(orb["atr"].iloc[-1])
            if np.isnan(atr_ref) or atr_ref < self.ATR_MIN:
                continue

            orb_atr = orb_range / atr_ref if atr_ref > 0 else np.nan
            if np.isnan(orb_atr) or orb_atr < self.MIN_ORB_ATR or orb_atr > self.MAX_ORB_ATR:
                continue

            trades_today = 0
            allow_buy = self._is_buy_allowed()
            allow_sell = self._is_sell_allowed()

            for i in range(1, len(session) - 1):
                if trades_today >= self.MAX_TRADES_DAY:
                    break

                row = session.iloc[i]
                prev = session.iloc[i - 1]
                next_row = session.iloc[i + 1]

                ts = session.index[i]
                entry_time = session.index[i + 1]

                if self._in_news_blackout(ts, news_events) or self._in_news_blackout(entry_time, news_events):
                    continue

                atr = float(row["atr"])
                if np.isnan(atr) or atr < self.ATR_MIN:
                    continue

                adx_h1 = float(row["h1_adx"])
                if np.isnan(adx_h1) or adx_h1 > self.ADX_MAX:
                    continue

                bull_regime = float(row["h1_ema_fast"]) > float(row["h1_ema_slow"])
                bear_regime = float(row["h1_ema_fast"]) < float(row["h1_ema_slow"])

                if self.USE_REGIME_FILTER:
                    long_context = (
                        bull_regime
                        and adx_h1 >= self.REGIME_ADX_MIN
                        and float(row["h1_ema_fast_slope_n"]) > 0
                        and float(row["h1_ema_spread_bull_atr"]) >= self.MIN_H1_EMA_SPREAD_ATR
                    )
                    short_context = (
                        bear_regime
                        and adx_h1 >= self.REGIME_ADX_MIN
                        and float(row["h1_ema_fast_slope_n"]) < 0
                        and float(row["h1_ema_spread_bear_atr"]) >= self.MIN_H1_EMA_SPREAD_ATR
                    )
                else:
                    long_context = bull_regime and adx_h1 >= self.ADX_MIN
                    short_context = bear_regime and adx_h1 >= self.ADX_MIN

                long_break = (
                    allow_buy
                    and long_context
                    and float(row["close"]) > orb_high + atr * self.BREAKOUT_BUFFER_ATR
                    and float(row["close"]) > float(row["open"])
                    and float(row["body_pct"]) >= self.BODY_PCT_MIN
                    and float(prev["close"]) <= orb_high
                )

                short_break = (
                    allow_sell
                    and short_context
                    and float(row["close"]) < orb_low - atr * self.BREAKOUT_BUFFER_ATR
                    and float(row["close"]) < float(row["open"])
                    and float(row["body_pct"]) >= self.BODY_PCT_MIN
                    and float(prev["close"]) >= orb_low
                )

                signal = None
                entry = None
                sl = None
                tp = None

                if long_break:
                    signal = "BUY"
                    entry = float(next_row["open"])

                    range_stop = orb_low - atr * 0.10
                    atr_stop = entry - atr * self.ATR_SL_MULT
                    sl = min(range_stop, atr_stop)
                    tp = entry + (entry - sl) * self.rr_ratio

                elif short_break:
                    signal = "SELL"
                    entry = float(next_row["open"])

                    range_stop = orb_high + atr * 0.10
                    atr_stop = entry + atr * self.ATR_SL_MULT
                    sl = max(range_stop, atr_stop)
                    tp = entry - (sl - entry) * self.rr_ratio

                if signal is None:
                    continue

                risk_distance = abs(entry - sl)
                if risk_distance <= 0 or np.isnan(risk_distance):
                    continue

                if signal == "BUY" and not (sl < entry < tp):
                    continue
                if signal == "SELL" and not (tp < entry < sl):
                    continue

                session_end_time = pd.Timestamp(entry_time.normalize()) + pd.Timedelta(hours=self.TRADE_END_HOUR)

                exit_time, exit_price, exit_reason, be_activated, best_r = self._simulate_trade_m1(
                    df_m1=df_m1,
                    signal_time=entry_time,
                    session_end_time=session_end_time,
                    signal_side=signal,
                    entry=entry,
                    sl=sl,
                    tp=tp,
                    risk_distance=risk_distance,
                )

                risk_amt = balance * self.risk_per_trade

                if exit_reason == "tp":
                    pnl = risk_amt * self.rr_ratio
                elif exit_reason == "sl":
                    pnl = -risk_amt
                elif exit_reason == "breakeven":
                    pnl = 0.0
                else:
                    if signal == "BUY":
                        r_multiple = (exit_price - entry) / risk_distance
                    else:
                        r_multiple = (entry - exit_price) / risk_distance
                    pnl = risk_amt * r_multiple

                pnl -= self.TRADE_COST_FIXED

                exit_reason_counter[exit_reason] = exit_reason_counter.get(exit_reason, 0) + 1
                side_counter[signal] = side_counter.get(signal, 0) + 1

                if be_activated:
                    be_activated_count += 1

                balance += pnl
                equity_curve.append(balance)

                trades.append(
                    {
                        "side": signal,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "entry": entry,
                        "exit": exit_price,
                        "sl": sl,
                        "tp": tp,
                        "pnl": pnl,
                        "exit_reason": exit_reason,
                        "be_activated": be_activated,
                        "best_r": round(float(best_r), 4),
                        "balance_after": balance,
                    }
                )

                trades_today += 1

        buy_trades = [t for t in trades if t["side"] == "BUY"]
        sell_trades = [t for t in trades if t["side"] == "SELL"]

        buy_wins = [t for t in buy_trades if t["pnl"] > 0]
        buy_losses = [t for t in buy_trades if t["pnl"] < 0]

        sell_wins = [t for t in sell_trades if t["pnl"] > 0]
        sell_losses = [t for t in sell_trades if t["pnl"] < 0]

        def _safe_pf(win_list, loss_list):
            gross_profit = float(sum(t["pnl"] for t in win_list))
            gross_loss = float(abs(sum(t["pnl"] for t in loss_list)))
            if gross_loss == 0:
                return float("inf") if gross_profit > 0 else 0.0
            return round(gross_profit / gross_loss, 3)

        def _safe_wr(side_trades, side_wins):
            if not side_trades:
                return 0.0
            return round(100.0 * len(side_wins) / len(side_trades), 2)

        def _safe_expectancy(side_trades):
            if not side_trades:
                return 0.0
            return round(float(np.mean([t["pnl"] for t in side_trades])), 2)

        self.last_diagnostics = {
            "trade_mode": self.trade_mode,
            "start_date": str(self.start_date) if self.start_date is not None else None,
            "end_date": str(self.end_date) if self.end_date is not None else None,
            "total_trades": len(trades),
            "exit_reason_counter": exit_reason_counter,
            "side_counter": side_counter,
            "be_activated_count": be_activated_count,
            "be_activation_rate_pct": round(
                100.0 * be_activated_count / len(trades), 2
            ) if trades else 0.0,
            "buy_stats": {
                "trades": len(buy_trades),
                "win_rate_pct": _safe_wr(buy_trades, buy_wins),
                "profit_factor": _safe_pf(buy_wins, buy_losses),
                "expectancy": _safe_expectancy(buy_trades),
            },
            "sell_stats": {
                "trades": len(sell_trades),
                "win_rate_pct": _safe_wr(sell_trades, sell_wins),
                "profit_factor": _safe_pf(sell_wins, sell_losses),
                "expectancy": _safe_expectancy(sell_trades),
            },
            "regime_filter": {
                "enabled": self.USE_REGIME_FILTER,
                "adx_min": self.REGIME_ADX_MIN,
                "h1_slope_lookback": self.H1_SLOPE_LOOKBACK,
                "min_h1_ema_spread_atr": self.MIN_H1_EMA_SPREAD_ATR,
            },
        }

        return self._compute_metrics(
            trades=trades,
            equity_curve=equity_curve,
            start_ts=df_m5.index[0] if len(df_m5) else None,
            end_ts=df_m5.index[-1] if len(df_m5) else None,
        )

    # =========================================================
    # Métricas
    # =========================================================
    def _compute_metrics(self, trades, equity_curve, start_ts=None, end_ts=None):
        if not trades:
            return BacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                total_return=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                expectancy=0.0,
                equity_curve=list(equity_curve) if equity_curve else [self.initial_balance],
            )

        pnls = np.array([float(t["pnl"]) for t in trades], dtype=float)

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]

        eq = np.array(equity_curve, dtype=float)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / np.where(peak == 0, 1.0, peak)
        max_dd = float(np.max(dd)) if len(dd) else 0.0

        daily_eq = self._build_daily_equity_curve(trades, start_ts, end_ts)
        if len(daily_eq) >= 2:
            daily_ret = daily_eq.pct_change().dropna().values
        else:
            daily_ret = np.array([], dtype=float)

        if len(daily_ret) == 0:
            sharpe = 0.0
            sortino = 0.0
        else:
            ret_mean = float(np.mean(daily_ret))
            ret_std = float(np.std(daily_ret, ddof=0))
            sharpe = 0.0 if ret_std == 0 else (ret_mean / ret_std) * np.sqrt(252)

            neg_ret = daily_ret[daily_ret < 0]
            neg_std = float(np.std(neg_ret, ddof=0)) if len(neg_ret) > 0 else 0.0
            if neg_std == 0:
                sortino = np.inf if ret_mean > 0 else 0.0
            else:
                sortino = (ret_mean / neg_std) * np.sqrt(252)

        gross_profit = float(sum(t["pnl"] for t in wins))
        gross_loss = float(abs(sum(t["pnl"] for t in losses)))

        if gross_loss == 0:
            profit_factor = np.inf if gross_profit > 0 else 0.0
        else:
            profit_factor = gross_profit / gross_loss

        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0

        return BacktestResult(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / len(trades) if trades else 0.0,
            profit_factor=round(float(profit_factor), 3) if np.isfinite(profit_factor) else np.inf,
            sharpe_ratio=round(float(sharpe), 3) if np.isfinite(sharpe) else np.inf,
            sortino_ratio=round(float(sortino), 3) if np.isfinite(sortino) else np.inf,
            max_drawdown=round(float(max_dd), 4),
            total_return=round(float((eq[-1] - eq[0]) / eq[0]), 4) if len(eq) >= 2 else 0.0,
            avg_win=round(float(avg_win), 2),
            avg_loss=round(float(avg_loss), 2),
            expectancy=round(float(np.mean(pnls)), 2),
            equity_curve=list(eq),
        )