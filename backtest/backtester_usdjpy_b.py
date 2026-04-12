# backtest/backtester_usdjpy_b.py — USDJPY Estrategia B: NY Open Range Breakout
#
# POR QUÉ CAMBIAMOS EL ENFOQUE:
#   El pullback a EMA21 en NY generaba WR 27-40% → no funciona para USDJPY
#   USDJPY en NY session sigue momentum, no revierte a EMAs en M5
#
# NUEVO ENFOQUE (misma lógica que Estrategia A, distinta ventana):
#   Estrategia A → Asian range (00-07 UTC), opera London (07-16 UTC)
#   Estrategia B → NY range    (13-14 UTC), opera NY     (14-18 UTC)
#
# LÓGICA:
#   1. Construir el rango de la primera hora de NY (13:00-14:00 UTC)
#   2. Detectar breakout del rango con buffer
#   3. Mismos filtros que A: ADX, ATR, body ratio, EMA de tendencia
#   4. Max 1 trade/día (complementario a Strategy A, no solapan)
#
# COMPLEMENTARIEDAD:
#   A opera: 07-16 UTC | B opera: 14-18 UTC
#   Solapan 14-16 UTC pero MAX_TRADES_DAY compartido controla el riesgo
#   Días sin señal en A → B puede disparar; días con señal en A → B es bonus

import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult


class USDJPYBacktesterB:
    # ── Indicadores ──
    EMA_FAST      = 20
    EMA_SLOW      = 100
    ADX_PERIOD    = 14
    ADX_MIN       = 15
    ADX_MAX       = 55
    ATR_PERIOD    = 14
    ATR_MIN       = 0.018
    ATR_SL_MULT   = 1.0

    # ── Rango NY (para construir el mini-rango de apertura) ──
    NY_RANGE_START = 13   # 13:00 UTC
    NY_RANGE_END   = 14   # 14:00 UTC (1 hora de rango)

    # ── Sesión de trading ──
    SESSION_START  = 14   # empezamos a operar al cierre del rango NY
    SESSION_END    = 18   # 18:00 UTC (cierre antes de fin de NY activo)

    # ── Gestión del trade ──
    RR_RATIO          = 1.5
    BUFFER_PIPS       = 0.03   # buffer sobre/bajo el rango para confirmar breakout
    MIN_BODY_RATIO    = 0.45   # vela de breakout con cuerpo claro
    MAX_BARS_IN_TRADE = 36     # máx 3h (36 × 5M)
    MAX_TRADES_DAY    = 1      # 1 trade/día (complementa Strategy A)
    FRIDAY_CUTOFF     = 16     # viernes cerrar antes

    # ── Filtros de calidad del rango ──
    RANGE_ATR_CAP     = 3.0    # rango NY no puede ser > 3×ATR (demasiado volátil)
    RANGE_MIN_PIPS    = 0.05   # rango mínimo para que valga la pena operar

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade:  float = 0.005,
        rr_ratio:        float = 1.5,
        symbol:          str   = "USDJPY",
        start_date:      str | None = None,
        end_date:        str | None = None,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade  = risk_per_trade
        self.rr_ratio        = rr_ratio
        self.symbol          = symbol
        self.start_date      = start_date
        self.end_date        = end_date
        self.last_trades_detail = []

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

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["ema_fast"] = df["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()

        hl  = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"]  - df["close"].shift()).abs()
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.ATR_PERIOD).mean()

        up   = df["high"].diff()
        down = -df["low"].diff()
        pdm  = np.where((up > down) & (up > 0), up, 0.0)
        mdm  = np.where((down > up) & (down > 0), down, 0.0)
        atr_s = tr.rolling(self.ADX_PERIOD).mean()
        pdi   = 100 * pd.Series(pdm, index=df.index).rolling(self.ADX_PERIOD).mean() / (atr_s + 1e-10)
        mdi   = 100 * pd.Series(mdm, index=df.index).rolling(self.ADX_PERIOD).mean() / (atr_s + 1e-10)
        dx    = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-10)
        df["adx"]      = dx.rolling(self.ADX_PERIOD).mean()
        df["plus_di"]  = pdi
        df["minus_di"] = mdi
        return df

    def _add_daily_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        df["hour"]    = df.index.hour
        df["date"]    = df.index.date
        df["weekday"] = df.index.weekday
        df["month"]   = df.index.month
        df["day"]     = df.index.day

        # Rango NY: high/low de la ventana 13:00-14:00 UTC
        df["ny_high"] = np.nan
        df["ny_low"]  = np.nan

        for date, grp in df.groupby("date"):
            ny = grp[(grp["hour"] >= self.NY_RANGE_START) &
                     (grp["hour"] <  self.NY_RANGE_END)]
            if len(ny) == 0:
                continue
            df.loc[df["date"] == date, "ny_high"] = float(ny["high"].max())
            df.loc[df["date"] == date, "ny_low"]  = float(ny["low"].min())

        df["ny_range"] = df["ny_high"] - df["ny_low"]
        return df

    def prepare_dataframe(self) -> pd.DataFrame:
        df = self.load_data()
        df = self._add_indicators(df)
        df = self._add_daily_levels(df)
        cols = ["open","high","low","close","atr","adx","ema_fast","ema_slow",
                "ny_high","ny_low","ny_range","hour","date","weekday"]
        return df.dropna(subset=cols)

    @staticmethod
    def _body_ratio(row: pd.Series) -> float:
        rng = float(row["high"] - row["low"])
        return 0.0 if rng < 1e-10 else abs(float(row["close"] - row["open"])) / rng

    # ─────────────────────────────────────────────
    # EJECUCIÓN DEL BACKTEST
    # ─────────────────────────────────────────────

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()
        print(f"{self.symbol} B (NY-ORB): {len(df)} velas | "
              f"{df.index.min()} → {df.index.max()}")

        balance       = self.initial_balance
        equity_curve  = [balance]
        trades        = []
        trades_detail = []
        trades_by_day = {}
        exit_stats    = {"tp": 0, "sl": 0, "timeout": 0}

        for i in range(120, len(df) - 5):
            row = df.iloc[i]

            # ── Filtros temporales ──
            if row["hour"] < self.SESSION_START or row["hour"] >= self.SESSION_END:
                continue
            if row["weekday"] >= 5:
                continue
            if row["weekday"] == 4 and row["hour"] >= self.FRIDAY_CUTOFF:
                continue
            is_xmas = (row["month"] == 12 and row["day"] >= 20) or \
                      (row["month"] == 1  and row["day"] <= 3)
            if is_xmas:
                continue

            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            # ── Filtros de indicadores ──
            curr_atr = float(row["atr"])
            if curr_atr < self.ATR_MIN:
                continue
            curr_adx = float(row["adx"])
            if curr_adx < self.ADX_MIN or curr_adx > self.ADX_MAX:
                continue

            # ── Calidad del rango NY ──
            ny_range = float(row["ny_range"])
            if ny_range <= self.RANGE_MIN_PIPS:
                continue
            if ny_range > curr_atr * self.RANGE_ATR_CAP:
                continue

            # ── Body ratio de la vela de breakout ──
            if self._body_ratio(row) < self.MIN_BODY_RATIO:
                continue

            # ── Detección de breakout del rango NY ──
            prev      = df.iloc[i - 1]
            ny_high   = float(row["ny_high"])
            ny_low    = float(row["ny_low"])
            prev_close = float(prev["close"])
            curr_close = float(row["close"])
            curr_high  = float(row["high"])
            curr_low   = float(row["low"])

            ema_bull = float(row["ema_fast"]) > float(row["ema_slow"])
            ema_bear = float(row["ema_fast"]) < float(row["ema_slow"])

            breakout_up = prev_close <= ny_high and \
                          curr_close > (ny_high + self.BUFFER_PIPS)
            breakout_dn = prev_close >= ny_low and \
                          curr_close < (ny_low  - self.BUFFER_PIPS)

            signal_val    = None
            entry         = curr_close
            sl            = None
            tp            = None
            risk_distance = None

            if breakout_up and ema_bull:
                signal_val    = "BUY"
                sl            = min(curr_low, ny_high) - self.BUFFER_PIPS
                risk_distance = entry - sl
                tp            = entry + risk_distance * self.rr_ratio

            elif breakout_dn and ema_bear:
                signal_val    = "SELL"
                sl            = max(curr_high, ny_low) + self.BUFFER_PIPS
                risk_distance = sl - entry
                tp            = entry - risk_distance * self.rr_ratio

            if not signal_val or risk_distance is None or risk_distance <= 0:
                continue

            # ── Gestión del trade ──
            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt    = balance * self.risk_per_trade
            won         = False
            exit_reason = "timeout"
            exit_time   = df.index[min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)]
            exit_price  = curr_close
            bars_held   = 0

            for j in range(i + 1, min(i + 1 + self.MAX_BARS_IN_TRADE, len(df))):
                fh = float(df.iloc[j]["high"])
                fl = float(df.iloc[j]["low"])
                bars_held = j - i

                if signal_val == "BUY":
                    if fh >= tp:
                        won = True; exit_reason = "tp"
                        exit_time = df.index[j]; exit_price = tp; break
                    if fl <= sl:
                        exit_reason = "sl"
                        exit_time = df.index[j]; exit_price = sl; break
                else:
                    if fl <= tp:
                        won = True; exit_reason = "tp"
                        exit_time = df.index[j]; exit_price = tp; break
                    if fh >= sl:
                        exit_reason = "sl"
                        exit_time = df.index[j]; exit_price = sl; break

            if exit_reason == "timeout":
                timeout_idx = min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)
                exit_time   = df.index[timeout_idx]
                exit_price  = float(df.iloc[timeout_idx]["close"])
                pnl = (exit_price - entry if signal_val == "BUY"
                       else entry - exit_price) / risk_distance * risk_amt
            elif won:
                pnl = risk_amt * self.rr_ratio
            else:
                pnl = -risk_amt

            balance_before = balance
            balance       += pnl
            equity_curve.append(balance)

            trades.append({"pnl": pnl, "won": won, "signal": signal_val,
                           "exit_reason": exit_reason})
            trades_detail.append({
                "entry_time":    df.index[i],
                "exit_time":     exit_time,
                "signal":        signal_val,
                "entry_price":   round(entry, 5),
                "sl_price":      round(sl, 5),
                "tp_price":      round(tp, 5),
                "exit_price":    round(float(exit_price), 5),
                "risk_distance": round(float(risk_distance), 5),
                "bars_held":     int(bars_held),
                "exit_reason":   exit_reason,
                "won":           bool(won),
                "adx":           round(float(curr_adx), 1),
                "atr":           round(float(curr_atr), 4),
                "ny_range":      round(float(ny_range), 5),
                "balance_before":round(float(balance_before), 2),
                "pnl":           round(float(pnl), 2),
                "balance_after": round(float(balance), 2),
            })
            exit_stats[exit_reason] += 1

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
        max_dd = float(np.max((peak - eq) / peak))

        rets   = np.diff(eq) / eq[:-1]
        sharpe = sortino = 0.0
        if len(rets) > 1:
            sharpe  = float(np.mean(rets)) / (float(np.std(rets)) + 1e-10) * np.sqrt(252)
            neg_r   = rets[rets < 0]
            sortino = float(np.mean(rets)) / (float(np.std(neg_r)) + 1e-10) * np.sqrt(252) \
                      if len(neg_r) > 0 else 0.0

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
            avg_win        = round(gp / (len(wins) + 1e-10), 2),
            avg_loss       = round(gl / (len(losses) + 1e-10), 2),
            expectancy     = round(float(np.mean(pnls)), 2),
            equity_curve   = list(eq),
        )
