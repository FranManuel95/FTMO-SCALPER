# backtest/backtester_mtf.py — Backtest MTF v2: EURUSD / GBPUSD
#
# DIAGNÓSTICO v1 → v2:
#   v1 problema: operar contra tendencia H4.
#   Jul 2025 EURUSD en tendencia alcista fuerte → el sistema metía SELLS → 25 SL de 32 trades.
#   Sin filtro H4: buenos meses WR 60-66%, malos meses WR 22-40%.
#   Con filtro H4: eliminamos trades contra tendencia dominante.
#
# CAMBIOS v2:
#   + H4 EMA20 como filtro de dirección (CAPA 0): solo BUY en H4 alcista, solo SELL en H4 bajista
#   + H1_ADX_MIN subido 18 → 25: solo operar en tendencias confirmadas, no en lateral
#   + LONDON_CLOSE = 12: solo primeras 5h de London (07-12 UTC), mayor momentum direccional
#   + MAX_TRADES_DAY = 1: evitar sobreoperar en días de reversión
#   - Eliminado modo PULLBACK standalone: solo CROSSOVER (limpia señales, mismo WR, menos ruido)
#
# 4 CAPAS DE FILTRADO:
#   H4  → Dirección macro (EMA20): determina BUY_ONLY o SELL_ONLY del día  ← NUEVA
#   1H  → Bias de tendencia (EMA200 + ADX25+): confirma estructura
#   15M → Confirmación setup (EMA20/50 + RSI + VWAP)
#   5M  → Entrada: cruce EMA9/21 en dirección H4+H1

import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult
from core.indicators import ema, adx, rsi, atr, vwap_ema


class MTFBacktester:

    # ── H4: dirección macro (NUEVO en v2) ─────────────────────────────────
    H4_EMA_DIR     = 20     # EMA20 en H4: define dirección del día

    # ── H1: bias de tendencia ──────────────────────────────────────────────
    H1_EMA_TREND   = 200
    H1_ADX_PERIOD  = 14
    H1_ADX_MIN     = 25    # v2: subido de 18→25 (solo tendencias confirmadas)
    H1_ADX_MAX     = 58

    # ── 15M: confirmación de setup ─────────────────────────────────────────
    M15_EMA_FAST   = 20
    M15_EMA_SLOW   = 50
    M15_RSI_PERIOD = 14

    # ── 5M: indicadores de entrada ─────────────────────────────────────────
    M5_EMA_ENTRY   = 9
    M5_EMA_CONFIRM = 21
    M5_ATR_PERIOD  = 14
    M5_RSI_PERIOD  = 14
    M5_ATR_MIN     = 0.0003

    # ── Sesiones UTC ───────────────────────────────────────────────────────
    LONDON_OPEN    = 7
    LONDON_CLOSE   = 12   # v2: solo mañana London (07-12), máximo momentum
    NY_OPEN        = 13
    NY_CLOSE       = 17   # v2: solo NY tarde (13-17)

    # ── Gestión del trade ──────────────────────────────────────────────────
    ATR_SL_MULT        = 1.2
    RR_RATIO           = 1.6
    BREAKEVEN_TRIGGER  = 1.0
    MAX_BARS_IN_TRADE  = 24
    MAX_TRADES_DAY     = 1   # v2: reducido de 2→1, máxima selectividad
    FRIDAY_CLOSE_HOUR  = 21

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
    # CARGA Y PREPARACIÓN
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
    def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """Construye barras de timeframe superior desde 5M. Barra etiquetada al open."""
        return df.resample(rule, label="left", closed="left").agg({
            "open": "first", "high": "max", "low": "min", "close": "last",
        }).dropna()

    def _h4_direction(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        Dirección macro H4: solo operamos en la dirección del trend dominante.
        h4_bull = close > EMA20(H4)  →  permitir BUY
        h4_bear = close < EMA20(H4)  →  permitir SELL
        Esto elimina trades contra-tendencia (principal causa de pérdidas en v1).
        """
        df = self._resample_ohlcv(df_5m, "4h").copy()
        df["ema20_h4"]  = ema(df["close"], self.H4_EMA_DIR)
        df["h4_bull"]   = df["close"] > df["ema20_h4"]
        df["h4_bear"]   = df["close"] < df["ema20_h4"]
        # shift(1): usamos la barra H4 ya cerrada, no la actual
        df["h4_bull"]   = df["h4_bull"].shift(1)
        df["h4_bear"]   = df["h4_bear"].shift(1)
        return df[["h4_bull", "h4_bear"]]

    def _h1_bias(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula bias alcista/bajista en H1.
        Usa shift(1) para garantizar que solo vemos velas H1 ya cerradas.
        """
        df = self._resample_ohlcv(df_5m, "1h").copy()
        close = df["close"]

        df["ema200"] = ema(close, self.H1_EMA_TREND)
        adx_df = adx(df, self.H1_ADX_PERIOD)
        df = pd.concat([df, adx_df], axis=1)

        in_regime   = df["adx"].between(self.H1_ADX_MIN, self.H1_ADX_MAX)
        df["bias_bull"] = (close > df["ema200"]) & in_regime & (df["plus_di"] > df["minus_di"])
        df["bias_bear"] = (close < df["ema200"]) & in_regime & (df["minus_di"] > df["plus_di"])

        # shift(1): en H1[N+1] usamos la señal de H1[N] (barra ya cerrada)
        df["bias_bull"] = df["bias_bull"].shift(1)
        df["bias_bear"] = df["bias_bear"].shift(1)

        return df[["bias_bull", "bias_bear"]]

    def _m15_setup(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula confirmación de setup en 15M.
        Usa shift(1) para garantizar que solo vemos velas 15M ya cerradas.
        """
        df = self._resample_ohlcv(df_5m, "15min").copy()
        close = df["close"]

        df["ema20"] = ema(close, self.M15_EMA_FAST)
        df["ema50"] = ema(close, self.M15_EMA_SLOW)
        df["rsi15"] = rsi(close, self.M15_RSI_PERIOD)
        df["vwap"]  = vwap_ema(close)

        df["setup_bull"] = (
            (df["ema20"] > df["ema50"]) &
            df["rsi15"].between(45, 75) &
            (close > df["vwap"] * 0.9998)
        )
        df["setup_bear"] = (
            (df["ema20"] < df["ema50"]) &
            df["rsi15"].between(25, 55) &
            (close < df["vwap"] * 1.0002)
        )

        df["setup_bull"] = df["setup_bull"].shift(1)
        df["setup_bear"] = df["setup_bear"].shift(1)

        return df[["setup_bull", "setup_bear"]]

    def prepare_dataframe(self) -> pd.DataFrame:
        """
        Ensambla el DataFrame 5M con todas las señales HTF alineadas causalmente.
        """
        df5 = self.load_data()
        print(f"{self.symbol} MTF: {len(df5)} velas | "
              f"{df5.index.min()} → {df5.index.max()}")

        # Señales HTF → reindex al índice 5M con forward-fill
        h4  = self._h4_direction(df5)   # capa 0: dirección macro
        h1  = self._h1_bias(df5)        # capa 1: bias tendencia
        m15 = self._m15_setup(df5)      # capa 2: confirmación setup

        df = df5.copy()
        df = df.join(h4.reindex(df.index,  method="ffill"), how="left")
        df = df.join(h1.reindex(df.index,  method="ffill"), how="left")
        df = df.join(m15.reindex(df.index, method="ffill"), how="left")

        # Indicadores 5M
        df["ema9"]  = ema(df["close"], self.M5_EMA_ENTRY)
        df["ema21"] = ema(df["close"], self.M5_EMA_CONFIRM)
        df["atr5"]  = atr(df, self.M5_ATR_PERIOD)
        df["rsi5"]  = rsi(df["close"], self.M5_RSI_PERIOD)

        # Campos temporales
        df["hour"]    = df.index.hour
        df["date"]    = df.index.date
        df["weekday"] = df.index.weekday
        df["month"]   = df.index.month
        df["day"]     = df.index.day

        # Sesión activa
        in_lon = (df["hour"] >= self.LONDON_OPEN) & (df["hour"] < self.LONDON_CLOSE)
        in_ny  = (df["hour"] >= self.NY_OPEN)     & (df["hour"] < self.NY_CLOSE)
        df["in_session"] = in_lon | in_ny

        # Rellenar booleans NaN con False
        for col in ["h4_bull", "h4_bear", "bias_bull", "bias_bear", "setup_bull", "setup_bear"]:
            df[col] = df[col].fillna(False)

        return df.dropna(subset=["ema9", "ema21", "atr5", "rsi5"])

    # ─────────────────────────────────────────────
    # SEÑALES DE ENTRADA
    # ─────────────────────────────────────────────

    def _crossover_signal(self, prev, curr) -> str | None:
        """Cruce EMA9/EMA21 en la última vela 5M."""
        p9, p21 = float(prev["ema9"]), float(prev["ema21"])
        c9, c21 = float(curr["ema9"]), float(curr["ema21"])
        if p9 <= p21 and c9 > c21:
            return "BUY"
        if p9 >= p21 and c9 < c21:
            return "SELL"
        return None

    def _pullback_signal(self, df: pd.DataFrame, i: int) -> str | None:
        """
        Precio retrocede a EMA21 en tendencia establecida (≥3 barras).
        Zona de pullback: precio dentro de ±0.5×ATR de EMA21.
        """
        curr  = df.iloc[i]
        close = float(curr["close"])
        ema21 = float(curr["ema21"])
        atr_v = float(curr["atr5"])

        near = abs(close - ema21) < atr_v * 0.5

        bull = all(float(df.iloc[k]["ema9"]) > float(df.iloc[k]["ema21"])
                   for k in range(i - 4, i - 1))
        bear = all(float(df.iloc[k]["ema9"]) < float(df.iloc[k]["ema21"])
                   for k in range(i - 4, i - 1))

        if bull and near and close > ema21:
            return "BUY"
        if bear and near and close < ema21:
            return "SELL"
        return None

    # ─────────────────────────────────────────────
    # EJECUCIÓN DEL BACKTEST
    # ─────────────────────────────────────────────

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()

        balance      = self.initial_balance
        equity_curve = [balance]
        trades: list[dict]        = []
        trades_detail: list[dict] = []
        trades_by_day: dict       = {}
        exit_stats = {"tp": 0, "sl": 0, "be": 0, "timeout": 0}

        for i in range(50, len(df) - 5):
            row = df.iloc[i]

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

            # ── Filtro de volatilidad ───────────────────────────────────────
            curr_atr = float(row["atr5"])
            if curr_atr < self.M5_ATR_MIN:
                continue

            # ── Contexto HTF (4 capas) ──────────────────────────────────────
            h4_bull    = bool(row["h4_bull"])     # capa 0: dirección macro H4
            h4_bear    = bool(row["h4_bear"])
            bias_bull  = bool(row["bias_bull"])   # capa 1: bias H1
            bias_bear  = bool(row["bias_bear"])
            setup_bull = bool(row["setup_bull"])  # capa 2: setup 15M
            setup_bear = bool(row["setup_bear"])
            rsi5       = float(row["rsi5"])
            entry      = float(row["close"])

            # ── Buscar señal (solo CROSSOVER, filtrado por H4+H1+15M) ──────
            signal = None
            mode   = None

            cross = self._crossover_signal(df.iloc[i - 1], row)
            # BUY: H4 alcista + H1 alcista + 15M alcista + RSI no sobrecomprado
            if (cross == "BUY" and h4_bull and bias_bull and setup_bull and rsi5 < 72):
                signal, mode = "BUY", "CROSS"
            # SELL: H4 bajista + H1 bajista + 15M bajista + RSI no sobrevendido
            elif (cross == "SELL" and h4_bear and bias_bear and setup_bear and rsi5 > 28):
                signal, mode = "SELL", "CROSS"

            if signal is None:
                continue

            # ── Setup de SL/TP ──────────────────────────────────────────────
            sl_dist = curr_atr * self.ATR_SL_MULT
            if signal == "BUY":
                sl = entry - sl_dist
                tp = entry + sl_dist * self.RR_RATIO
            else:
                sl = entry + sl_dist
                tp = entry - sl_dist * self.RR_RATIO

            # ── Simular el trade ────────────────────────────────────────────
            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt    = balance * self.risk_per_trade
            won         = False
            exit_reason = "timeout"
            exit_time   = df.index[min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)]
            exit_price  = entry
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
                        be_sl = entry + curr_atr * 0.1
                    active_sl = be_sl if be_activated else sl
                    if fl <= active_sl:
                        exit_reason = "be" if be_activated else "sl"
                        won = be_activated
                        exit_time = df.index[j]; exit_price = active_sl; break
                    if fh >= tp:
                        won = True; exit_reason = "tp"
                        exit_time = df.index[j]; exit_price = tp; break
                else:
                    if not be_activated and fl <= entry - sl_dist * self.BREAKEVEN_TRIGGER:
                        be_activated = True
                        be_sl = entry - curr_atr * 0.1
                    active_sl = be_sl if be_activated else sl
                    if fh >= active_sl:
                        exit_reason = "be" if be_activated else "sl"
                        won = be_activated
                        exit_time = df.index[j]; exit_price = active_sl; break
                    if fl <= tp:
                        won = True; exit_reason = "tp"
                        exit_time = df.index[j]; exit_price = tp; break

            # ── P&L ─────────────────────────────────────────────────────────
            if exit_reason == "timeout":
                idx = min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)
                exit_time  = df.index[idx]
                exit_price = float(df.iloc[idx]["close"])
                raw = (exit_price - entry if signal == "BUY" else entry - exit_price)
                pnl = raw / sl_dist * risk_amt
            elif exit_reason == "tp":
                pnl = risk_amt * self.RR_RATIO
            elif exit_reason == "be":
                pnl = max(abs(float(exit_price) - entry) / sl_dist * risk_amt, 0)
            else:  # sl
                pnl = -risk_amt

            balance_before = balance
            balance       += pnl
            equity_curve.append(balance)
            exit_stats[exit_reason] += 1

            trades.append({
                "pnl": pnl, "won": won,
                "signal": signal, "exit_reason": exit_reason,
            })
            trades_detail.append({
                "entry_time":    df.index[i],
                "exit_time":     exit_time,
                "signal":        signal,
                "mode":          mode,
                "entry_price":   round(entry, 5),
                "sl_price":      round(sl, 5),
                "tp_price":      round(tp, 5),
                "exit_price":    round(float(exit_price), 5),
                "sl_dist":       round(sl_dist, 5),
                "bars_held":     int(bars_held),
                "exit_reason":   exit_reason,
                "won":           bool(won),
                "atr5":          round(curr_atr, 5),
                "rsi5":          round(rsi5, 1),
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
