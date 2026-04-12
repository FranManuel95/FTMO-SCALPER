# backtest/backtester_mtf.py — MTF Top-Down con Patrones de Vela
#
# ESTRUCTURA (top-down, 4 capas):
#
#   H1   → Tendencia macro: precio respecto a EMA50+EMA200
#           BUY  : close > EMA50 > EMA200 (estructura alcista completa)
#           SELL : close < EMA50 < EMA200 (estructura bajista completa)
#
#   M15  → Confirmación: misma condición EMA50+EMA200 en timeframe medio
#           Alinea el trade con la tendencia intermedia
#
#   M5   → Filtro de momentum: RSI + VWAP
#           BUY  : RSI 40-70 (no sobrecomprado) + close > VWAP
#           SELL : RSI 30-60 (no sobrevendido)  + close < VWAP
#
#   M5   → Entrada: patrón de vela en zona S/R (EMA50/200 en M5)
#           Zona BUY  : precio cerca de EMA50_M5 o EMA200_M5 como soporte
#           Zona SELL : precio cerca de EMA50_M5 o EMA200_M5 como resistencia
#           Gatillos BUY  : vela envolvente alcista | martillo
#           Gatillos SELL : vela envolvente bajista | shooting star
#
# SL: estructural — debajo del mínimo de la vela gatillo (BUY)
#                   encima del máximo de la vela gatillo (SELL)
# TP: RR 2.0 desde el SL estructural
#
# ALINEACIÓN CAUSAL: shift(1) + reindex(ffill) → sin lookahead

import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult
from core.indicators import ema, rsi, atr, vwap_ema


class MTFBacktester:

    # ── H1 ─────────────────────────────────────────────────────────────────
    H1_EMA_FAST    = 50
    H1_EMA_SLOW    = 200

    # ── M15 ────────────────────────────────────────────────────────────────
    M15_EMA_FAST   = 50
    M15_EMA_SLOW   = 200

    # ── M5 momentum ────────────────────────────────────────────────────────
    M5_RSI_PERIOD  = 14
    M5_ATR_PERIOD  = 14
    M5_EMA_FAST    = 50     # S/R dinámico en M5
    M5_EMA_SLOW    = 200    # S/R dinámico en M5
    M5_ATR_MIN     = 0.0003

    # ── Zona S/R: precio dentro de N×ATR de EMA para considerar toque ──────
    SR_ZONE_ATR    = 0.4    # 0.4×ATR alrededor de EMA50/200 (ajustado de 0.6)

    # ── Patrones de vela ───────────────────────────────────────────────────
    ENGULF_MIN_RATIO = 1.05  # cuerpo engullidor ≥ 105% del cuerpo anterior
    HAMMER_WICK_MULT = 1.8   # mecha ≥ 1.8× el cuerpo
    MIN_CANDLE_ATR   = 0.15  # rango mínimo de la vela gatillo (% del ATR)

    # ── Sesiones UTC ───────────────────────────────────────────────────────
    LONDON_OPEN    = 7
    LONDON_CLOSE   = 17
    NY_OPEN        = 13
    NY_CLOSE       = 20

    # ── Gestión ────────────────────────────────────────────────────────────
    RR_RATIO           = 1.5
    SL_BUFFER_ATR      = 0.10   # buffer extra debajo/encima del mínimo/máximo
    MAX_SL_ATR         = 1.2    # SL máximo en ATR: evita entradas con SL >~8 pips
    MAX_BARS_IN_TRADE  = 36     # 3h máximo
    MAX_TRADES_DAY     = 2
    FRIDAY_CLOSE_HOUR  = 21
    BREAKEVEN_TRIGGER  = 1.0    # mover SL a BE cuando ganancia ≥ 1.0R

    def __init__(
        self,
        symbol:          str   = "EURUSD",
        initial_balance: float = 10_000,
        risk_per_trade:  float = 0.005,
        start_date:      str | None = None,
        end_date:        str | None = None,
    ):
        self.symbol          = symbol
        self.initial_balance = initial_balance
        self.risk_per_trade  = risk_per_trade
        self.start_date      = start_date
        self.end_date        = end_date
        self.last_trades_detail: list[dict] = []

    # ─────────────────────────────────────────────
    # CARGA
    # ─────────────────────────────────────────────

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(
            f"backtest/data/{self.symbol}_5M.csv",
            index_col=0, parse_dates=True,
        )
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()
        if self.start_date:
            df = df[df.index >= pd.Timestamp(self.start_date)]
        if self.end_date:
            df = df[df.index <= pd.Timestamp(self.end_date)]
        return df

    @staticmethod
    def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        return df.resample(rule, label="left", closed="left").agg({
            "open": "first", "high": "max", "low": "min", "close": "last",
        }).dropna()

    # ─────────────────────────────────────────────
    # CAPAS HTF
    # ─────────────────────────────────────────────

    def _h1_trend(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        H1: estructura de tendencia EMA50/200.
        BUY  → close > EMA50 > EMA200
        SELL → close < EMA50 < EMA200
        """
        df = self._resample(df_5m, "1h").copy()
        df["e50"]  = ema(df["close"], self.H1_EMA_FAST)
        df["e200"] = ema(df["close"], self.H1_EMA_SLOW)

        df["h1_bull"] = (df["close"] > df["e50"]) & (df["e50"] > df["e200"])
        df["h1_bear"] = (df["close"] < df["e50"]) & (df["e50"] < df["e200"])

        df["h1_bull"] = df["h1_bull"].shift(1)
        df["h1_bear"] = df["h1_bear"].shift(1)
        return df[["h1_bull", "h1_bear"]]

    def _m15_trend(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        M15: confirmación de tendencia con EMA50/200.
        Precio debe estar al mismo lado que en H1.
        """
        df = self._resample(df_5m, "15min").copy()
        df["e50"]  = ema(df["close"], self.M15_EMA_FAST)
        df["e200"] = ema(df["close"], self.M15_EMA_SLOW)

        df["m15_bull"] = (df["close"] > df["e50"]) & (df["close"] > df["e200"])
        df["m15_bear"] = (df["close"] < df["e50"]) & (df["close"] < df["e200"])

        df["m15_bull"] = df["m15_bull"].shift(1)
        df["m15_bear"] = df["m15_bear"].shift(1)
        return df[["m15_bull", "m15_bear"]]

    # ─────────────────────────────────────────────
    # PREPARACIÓN COMPLETA DEL DATAFRAME
    # ─────────────────────────────────────────────

    def prepare_dataframe(self) -> pd.DataFrame:
        df5 = self.load_data()
        print(f"{self.symbol} MTF: {len(df5)} velas | "
              f"{df5.index.min()} → {df5.index.max()}")

        h1  = self._h1_trend(df5)
        m15 = self._m15_trend(df5)

        df = df5.copy()
        df = df.join(h1.reindex(df.index,  method="ffill"), how="left")
        df = df.join(m15.reindex(df.index, method="ffill"), how="left")

        # Indicadores M5
        df["ema50"]  = ema(df["close"], self.M5_EMA_FAST)
        df["ema200"] = ema(df["close"], self.M5_EMA_SLOW)
        df["rsi5"]   = rsi(df["close"], self.M5_RSI_PERIOD)
        df["atr5"]   = atr(df, self.M5_ATR_PERIOD)
        df["vwap5"]  = vwap_ema(df["close"])

        # Campos temporales
        df["hour"]    = df.index.hour
        df["date"]    = df.index.date
        df["weekday"] = df.index.weekday
        df["month"]   = df.index.month
        df["day"]     = df.index.day

        in_lon = (df["hour"] >= self.LONDON_OPEN) & (df["hour"] < self.LONDON_CLOSE)
        in_ny  = (df["hour"] >= self.NY_OPEN)     & (df["hour"] < self.NY_CLOSE)
        df["in_session"] = in_lon | in_ny

        for col in ["h1_bull", "h1_bear", "m15_bull", "m15_bear"]:
            df[col] = df[col].fillna(False)

        return df.dropna(subset=["ema50", "ema200", "rsi5", "atr5", "vwap5"])

    # ─────────────────────────────────────────────
    # PATRONES DE VELA
    # ─────────────────────────────────────────────

    @staticmethod
    def _body(c: pd.Series) -> float:
        return abs(float(c["close"]) - float(c["open"]))

    @staticmethod
    def _is_bull_candle(c: pd.Series) -> bool:
        return float(c["close"]) > float(c["open"])

    @staticmethod
    def _is_bear_candle(c: pd.Series) -> bool:
        return float(c["close"]) < float(c["open"])

    def _bull_engulfing(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Envolvente alcista: vela verde que engloba completamente la vela roja anterior."""
        if not (self._is_bear_candle(prev) and self._is_bull_candle(curr)):
            return False
        prev_body = self._body(prev)
        curr_body = self._body(curr)
        if prev_body < 1e-8:
            return False
        # Cuerpo actual engloba cuerpo anterior
        engulfs = (float(curr["open"]) <= float(prev["close"]) and
                   float(curr["close"]) >= float(prev["open"]))
        return engulfs and curr_body >= prev_body * self.ENGULF_MIN_RATIO

    def _bear_engulfing(self, prev: pd.Series, curr: pd.Series) -> bool:
        """Envolvente bajista: vela roja que engloba completamente la vela verde anterior."""
        if not (self._is_bull_candle(prev) and self._is_bear_candle(curr)):
            return False
        prev_body = self._body(prev)
        curr_body = self._body(curr)
        if prev_body < 1e-8:
            return False
        engulfs = (float(curr["open"]) >= float(prev["close"]) and
                   float(curr["close"]) <= float(prev["open"]))
        return engulfs and curr_body >= prev_body * self.ENGULF_MIN_RATIO

    def _hammer(self, c: pd.Series) -> bool:
        """
        Martillo alcista: mecha inferior ≥ 1.8× cuerpo, mecha superior pequeña.
        Señal de rechazo de soporte.
        """
        body  = self._body(c)
        if body < 1e-8:
            return False
        low_wick  = min(float(c["open"]), float(c["close"])) - float(c["low"])
        high_wick = float(c["high"]) - max(float(c["open"]), float(c["close"]))
        return (low_wick >= body * self.HAMMER_WICK_MULT and
                high_wick <= body * 0.5)

    def _shooting_star(self, c: pd.Series) -> bool:
        """
        Shooting star bajista: mecha superior ≥ 1.8× cuerpo, mecha inferior pequeña.
        Señal de rechazo de resistencia.
        """
        body = self._body(c)
        if body < 1e-8:
            return False
        high_wick = float(c["high"]) - max(float(c["open"]), float(c["close"]))
        low_wick  = min(float(c["open"]), float(c["close"])) - float(c["low"])
        return (high_wick >= body * self.HAMMER_WICK_MULT and
                low_wick <= body * 0.5)

    def _has_bull_trigger(self, prev: pd.Series, curr: pd.Series) -> str | None:
        """Retorna nombre del patrón alcista, o None si no hay."""
        if self._bull_engulfing(prev, curr):
            return "ENGULF_BULL"
        if self._hammer(curr):
            return "HAMMER"
        return None

    def _has_bear_trigger(self, prev: pd.Series, curr: pd.Series) -> str | None:
        """Retorna nombre del patrón bajista, o None si no hay."""
        if self._bear_engulfing(prev, curr):
            return "ENGULF_BEAR"
        if self._shooting_star(curr):
            return "SHOOT_STAR"
        return None

    # ─────────────────────────────────────────────
    # ZONA S/R EN M5
    # ─────────────────────────────────────────────

    def _near_support(self, close: float, ema50: float, ema200: float,
                      atr_val: float) -> bool:
        """
        Precio cerca de EMA50_M5 o EMA200_M5 como soporte.
        'Cerca' = dentro de SR_ZONE_ATR × ATR de la EMA.
        Precio puede estar ligeramente por debajo (hasta 0.5×zone) para
        capturar rechazos que perforan brevemente el nivel.
        """
        zone = atr_val * self.SR_ZONE_ATR
        # Precio ≥ EMA - 0.5×zone (no más de medio zone por debajo)
        near50  = abs(close - ema50)  < zone and close >= ema50  - zone * 0.5
        near200 = abs(close - ema200) < zone and close >= ema200 - zone * 0.5
        return near50 or near200

    def _near_resistance(self, close: float, ema50: float, ema200: float,
                         atr_val: float) -> bool:
        """
        Precio cerca de EMA50_M5 o EMA200_M5 como resistencia.
        Precio puede estar ligeramente por encima (hasta 0.5×zone) para
        capturar rechazos que perforan brevemente el nivel.
        """
        zone = atr_val * self.SR_ZONE_ATR
        near50  = abs(close - ema50)  < zone and close <= ema50  + zone * 0.5
        near200 = abs(close - ema200) < zone and close <= ema200 + zone * 0.5
        return near50 or near200

    # ─────────────────────────────────────────────
    # BACKTEST
    # ─────────────────────────────────────────────

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()

        balance      = self.initial_balance
        equity_curve = [balance]
        trades: list[dict]        = []
        trades_detail: list[dict] = []
        trades_by_day: dict       = {}
        exit_stats = {"tp": 0, "sl": 0, "be": 0, "timeout": 0}

        for i in range(250, len(df) - 5):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]

            # ── Filtros temporales ──────────────────────────────────────────
            if not row["in_session"]:
                continue
            if row["weekday"] >= 5:
                continue
            if row["weekday"] == 4 and row["hour"] >= self.FRIDAY_CLOSE_HOUR:
                continue
            is_xmas = (row["month"] == 12 and row["day"] >= 20) or \
                      (row["month"] == 1  and row["day"] <= 3)
            if is_xmas:
                continue

            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            # ── Volatilidad mínima ──────────────────────────────────────────
            curr_atr = float(row["atr5"])
            if curr_atr < self.M5_ATR_MIN:
                continue

            # ── Capas HTF ───────────────────────────────────────────────────
            h1_bull  = bool(row["h1_bull"])
            h1_bear  = bool(row["h1_bear"])
            m15_bull = bool(row["m15_bull"])
            m15_bear = bool(row["m15_bear"])

            # ── Momentum M5 ─────────────────────────────────────────────────
            rsi5     = float(row["rsi5"])
            close    = float(row["close"])
            vwap     = float(row["vwap5"])
            ema50    = float(row["ema50"])
            ema200   = float(row["ema200"])

            rsi_bull = 35 <= rsi5 <= 65
            rsi_bear = 35 <= rsi5 <= 65
            vwap_bull = close > vwap
            vwap_bear = close < vwap

            # ── Alineación EMA en M5 (confirma mini-tendencia) ──────────────
            m5_ema_bull = ema50 > ema200
            m5_ema_bear = ema50 < ema200

            # ── Tamaño mínimo de la vela (filtra dojis y microvelas) ─────────
            curr_range = float(row["high"]) - float(row["low"])
            if curr_range < curr_atr * self.MIN_CANDLE_ATR:
                continue

            # ── Zona S/R en M5 ──────────────────────────────────────────────
            near_sup = self._near_support(close, ema50, ema200, curr_atr)
            near_res = self._near_resistance(close, ema50, ema200, curr_atr)

            # ── Patrones de vela (gatillo) ──────────────────────────────────
            bull_pattern = self._has_bull_trigger(prev, row)
            bear_pattern = self._has_bear_trigger(prev, row)

            # ── Señal final (todas las capas deben alinearse) ───────────────
            signal  = None
            pattern = None

            if (h1_bull and m15_bull and m5_ema_bull and rsi_bull and vwap_bull and
                    near_sup and bull_pattern):
                signal  = "BUY"
                pattern = bull_pattern

            elif (h1_bear and m15_bear and m5_ema_bear and rsi_bear and vwap_bear and
                    near_res and bear_pattern):
                signal  = "SELL"
                pattern = bear_pattern

            if signal is None:
                continue

            # ── SL estructural (bajo/alto de la vela gatillo) ───────────────
            if signal == "BUY":
                sl = float(row["low"]) - curr_atr * self.SL_BUFFER_ATR
                entry = close
            else:
                sl = float(row["high"]) + curr_atr * self.SL_BUFFER_ATR
                entry = close

            sl_dist = abs(entry - sl)

            # Descartar si SL es absurdamente grande
            if sl_dist > curr_atr * self.MAX_SL_ATR or sl_dist <= 0:
                continue

            tp = entry + sl_dist * self.RR_RATIO if signal == "BUY" \
                 else entry - sl_dist * self.RR_RATIO

            # ── Simulación ──────────────────────────────────────────────────
            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt    = balance * self.risk_per_trade
            won         = False
            exit_reason = "timeout"
            exit_price  = close
            bars_held   = 0
            be_activated = False
            be_sl        = sl

            for j in range(i + 1, min(i + 1 + self.MAX_BARS_IN_TRADE, len(df))):
                fh = float(df.iloc[j]["high"])
                fl = float(df.iloc[j]["low"])
                bars_held = j - i

                if signal == "BUY":
                    if not be_activated and fh >= entry + sl_dist * self.BREAKEVEN_TRIGGER:
                        be_activated = True
                        be_sl = entry + curr_atr * 0.05
                    active_sl = be_sl if be_activated else sl
                    if fl <= active_sl:
                        exit_reason = "be" if be_activated else "sl"
                        won = be_activated
                        exit_price = active_sl
                        break
                    if fh >= tp:
                        won = True; exit_reason = "tp"
                        exit_price = tp; break
                else:
                    if not be_activated and fl <= entry - sl_dist * self.BREAKEVEN_TRIGGER:
                        be_activated = True
                        be_sl = entry - curr_atr * 0.05
                    active_sl = be_sl if be_activated else sl
                    if fh >= active_sl:
                        exit_reason = "be" if be_activated else "sl"
                        won = be_activated
                        exit_price = active_sl
                        break
                    if fl <= tp:
                        won = True; exit_reason = "tp"
                        exit_price = tp; break

            # ── P&L ─────────────────────────────────────────────────────────
            if exit_reason == "timeout":
                idx = min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)
                exit_price = float(df.iloc[idx]["close"])
                raw = exit_price - entry if signal == "BUY" else entry - exit_price
                pnl = raw / sl_dist * risk_amt
            elif exit_reason == "tp":
                pnl = risk_amt * self.RR_RATIO
            elif exit_reason == "be":
                pnl = max(abs(float(exit_price) - entry) / sl_dist * risk_amt, 0)
            else:
                pnl = -risk_amt

            balance_before = balance
            balance       += pnl
            equity_curve.append(balance)
            exit_stats[exit_reason] += 1

            trades.append({"pnl": pnl, "won": won,
                           "signal": signal, "exit_reason": exit_reason})
            trades_detail.append({
                "entry_time":    df.index[i],
                "signal":        signal,
                "pattern":       pattern,
                "entry_price":   round(entry, 5),
                "sl_price":      round(sl, 5),
                "tp_price":      round(tp, 5),
                "exit_price":    round(float(exit_price), 5),
                "sl_dist":       round(sl_dist, 5),
                "sl_dist_pips":  round(sl_dist / 0.0001, 1),
                "bars_held":     int(bars_held),
                "exit_reason":   exit_reason,
                "won":           bool(won),
                "rsi5":          round(rsi5, 1),
                "atr5":          round(curr_atr, 5),
                "pnl":           round(pnl, 2),
                "balance_before":round(balance_before, 2),
                "balance_after": round(balance, 2),
            })

        self.last_trades_detail = trades_detail
        result = self._compute_metrics(trades, equity_curve)
        result.extra_stats = exit_stats
        return result

    # ─────────────────────────────────────────────
    # MÉTRICAS
    # ─────────────────────────────────────────────

    def _compute_metrics(self, trades, equity_curve) -> BacktestResult:
        if not trades:
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0.0, profit_factor=0.0, sharpe_ratio=0.0,
                sortino_ratio=0.0, max_drawdown=0.0, total_return=0.0,
                avg_win=0.0, avg_loss=0.0, expectancy=0.0,
                equity_curve=list(equity_curve),
            )

        pnls   = np.array([t["pnl"] for t in trades], dtype=float)
        wins   = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]
        eq     = np.array(equity_curve, dtype=float)

        peak   = np.maximum.accumulate(eq)
        max_dd = float(np.max((peak - eq) / (peak + 1e-10)))

        rets   = np.diff(eq) / (eq[:-1] + 1e-10)
        sharpe = sortino = 0.0
        if len(rets) > 1 and np.std(rets) > 0:
            sharpe  = float(np.mean(rets)) / float(np.std(rets)) * np.sqrt(252 * 78)
            neg_r   = rets[rets < 0]
            if len(neg_r) > 0 and np.std(neg_r) > 0:
                sortino = float(np.mean(rets)) / float(np.std(neg_r)) * np.sqrt(252 * 78)

        gp = sum(t["pnl"] for t in wins)
        gl = abs(sum(t["pnl"] for t in losses))

        return BacktestResult(
            total_trades   = len(trades),
            winning_trades = len(wins),
            losing_trades  = len(losses),
            win_rate       = len(wins) / len(trades),
            profit_factor  = round(gp / (gl + 1e-10), 3),
            sharpe_ratio   = round(sharpe, 3),
            sortino_ratio  = round(sortino, 3),
            max_drawdown   = round(max_dd, 4),
            total_return   = round((eq[-1] - eq[0]) / eq[0], 4),
            avg_win        = round(gp / (len(wins)   + 1e-10), 2),
            avg_loss       = round(gl / (len(losses) + 1e-10), 2),
            expectancy     = round(float(np.mean(pnls)), 2),
            equity_curve   = list(eq),
        )
