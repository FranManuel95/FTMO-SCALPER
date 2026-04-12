# backtest/backtester_mtf.py — MTF Top-Down con EMA Cross en M5
#
# ESTRUCTURA (top-down, 4 capas):
#
#   H1   → Tendencia macro: precio respecto a EMA50+EMA200
#           BUY  : close > EMA50 > EMA200 (estructura alcista completa)
#           SELL : close < EMA50 < EMA200 (estructura bajista completa)
#           ADX  : > 20 (filtra mercados sin tendencia real)
#
#   M15  → Confirmación: misma condición EMA50+EMA200 en timeframe medio
#
#   M5   → Momentum: RSI 40-68 (BUY) / 32-60 (SELL) + close vs VWAP
#
#   M5   → ENTRADA: EMA9 cruza EMA21 en la dirección del trend
#           BUY  : EMA9 cruza ARRIBA de EMA21 (momentum alcista se reanuda)
#           SELL : EMA9 cruza ABAJO de EMA21 (momentum bajista se reanuda)
#
# SL : justo bajo EMA21 – SL_BELOW_EMA_ATR × ATR (BUY)
#       justo sobre EMA21 + SL_BELOW_EMA_ATR × ATR (SELL)
# TP : RR × distancia al SL
#
# RAZONAMIENTO:
#   En H1+M15 uptrend, el precio hace pullbacks y luego reanuda.
#   Cuando EMA9 cruza EMA21 de nuevo al alza, el pullback ha terminado
#   y la tendencia se reanuda. El SL bajo EMA21 es lógico: si el precio
#   vuelve a cruzar EMA21 a la baja, el cross fue falso → salir.
#
# ALINEACIÓN CAUSAL: shift(1) en HTF + comparación con prev en M5.

import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult
from core.indicators import ema, rsi, atr, vwap_ema, adx as adx_ind


class MTFBacktester:

    # ── H1 ─────────────────────────────────────────────────────────────────
    H1_EMA_FAST    = 50
    H1_EMA_SLOW    = 200
    H1_ADX_MIN     = 20      # ADX mínimo en H1: filtra rangos

    # ── M15 ────────────────────────────────────────────────────────────────
    M15_EMA_FAST   = 50
    M15_EMA_SLOW   = 200

    # ── M5 momentum + entrada ──────────────────────────────────────────────
    M5_EMA_FAST    = 9       # EMA de entrada (cross trigger)
    M5_EMA_SLOW    = 21      # EMA de confirmación (soporte/resistencia)
    M5_RSI_PERIOD  = 14
    M5_ATR_PERIOD  = 14
    M5_ATR_MIN     = 0.0003

    # ── Sesiones UTC ───────────────────────────────────────────────────────
    LONDON_OPEN    = 7
    LONDON_CLOSE   = 17
    NY_OPEN        = 13
    NY_CLOSE       = 20

    # ── Gestión ────────────────────────────────────────────────────────────
    RR_RATIO           = 1.5
    SL_BELOW_EMA_ATR   = 0.3    # SL = EMA21 − 0.3×ATR (BUY)
    MAX_SL_ATR         = 1.0    # Rechaza entradas con SL > 1×ATR (~7 pips)
    MAX_BARS_IN_TRADE  = 36     # 3h máximo
    MAX_TRADES_DAY     = 3
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
        H1: estructura de tendencia EMA50/200 + ADX para medir fuerza.
        BUY  → close > EMA50 > EMA200 AND ADX > H1_ADX_MIN
        SELL → close < EMA50 < EMA200 AND ADX > H1_ADX_MIN
        """
        df = self._resample(df_5m, "1h").copy()
        df["e50"]  = ema(df["close"], self.H1_EMA_FAST)
        df["e200"] = ema(df["close"], self.H1_EMA_SLOW)

        adx_df       = adx_ind(df, 14)
        df["h1_adx"] = adx_df["adx"]

        df["h1_bull"] = (df["close"] > df["e50"]) & (df["e50"] > df["e200"])
        df["h1_bear"] = (df["close"] < df["e50"]) & (df["e50"] < df["e200"])

        for col in ["h1_bull", "h1_bear", "h1_adx"]:
            df[col] = df[col].shift(1)

        return df[["h1_bull", "h1_bear", "h1_adx"]]

    def _m15_trend(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        M15: confirmación de tendencia con EMA50/200.
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
        df["ema9"]  = ema(df["close"], self.M5_EMA_FAST)
        df["ema21"] = ema(df["close"], self.M5_EMA_SLOW)
        df["rsi5"]  = rsi(df["close"], self.M5_RSI_PERIOD)
        df["atr5"]  = atr(df, self.M5_ATR_PERIOD)
        df["vwap5"] = vwap_ema(df["close"])

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

        return df.dropna(subset=["ema9", "ema21", "rsi5", "atr5", "vwap5"])

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

            # ── Filtro ADX H1 ───────────────────────────────────────────────
            h1_adx = float(row["h1_adx"]) if not pd.isna(row["h1_adx"]) else 0.0
            if h1_adx < self.H1_ADX_MIN:
                continue

            # ── M5: cross EMA9/EMA21 (gatillo de entrada) ───────────────────
            ema9_curr  = float(row["ema9"])
            ema21_curr = float(row["ema21"])
            ema9_prev  = float(prev["ema9"])
            ema21_prev = float(prev["ema21"])

            cross_up   = (ema9_curr > ema21_curr) and (ema9_prev <= ema21_prev)
            cross_down = (ema9_curr < ema21_curr) and (ema9_prev >= ema21_prev)

            if not (cross_up or cross_down):
                continue

            # ── M5 momentum ─────────────────────────────────────────────────
            rsi5      = float(row["rsi5"])
            close     = float(row["close"])
            vwap      = float(row["vwap5"])

            rsi_bull  = 40 <= rsi5 <= 68
            rsi_bear  = 32 <= rsi5 <= 60
            vwap_bull = close > vwap
            vwap_bear = close < vwap

            # ── Señal final ─────────────────────────────────────────────────
            signal = None

            if cross_up  and h1_bull and m15_bull and rsi_bull and vwap_bull:
                signal = "BUY"
            elif cross_down and h1_bear and m15_bear and rsi_bear and vwap_bear:
                signal = "SELL"

            if signal is None:
                continue

            # ── SL bajo/sobre EMA21 ─────────────────────────────────────────
            # Lógica: si el precio vuelve a cruzar EMA21 en contra, el setup falló.
            # Añadimos un pequeño buffer bajo EMA21 para evitar ruido.
            entry = close
            if signal == "BUY":
                sl = ema21_curr - curr_atr * self.SL_BELOW_EMA_ATR
                # También verificar que el SL esté por debajo del mínimo de la vela
                sl = min(sl, float(row["low"]) - curr_atr * 0.05)
            else:
                sl = ema21_curr + curr_atr * self.SL_BELOW_EMA_ATR
                sl = max(sl, float(row["high"]) + curr_atr * 0.05)

            sl_dist = abs(entry - sl)

            # Rechazar si SL es demasiado grande o inválido
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
                "h1_adx":        round(h1_adx, 1),
                "ema9":          round(ema9_curr, 5),
                "ema21":         round(ema21_curr, 5),
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
