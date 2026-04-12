# backtest/backtester_usdjpy_b.py — USDJPY Estrategia B: NY Continuation
#
# CONCEPTO:
#   Estrategia A (rango asiático) opera en London (07-16 UTC) → alta calidad, baja frecuencia
#   Estrategia B opera en NY (13-20 UTC) → más frecuente, dirección alineada con tendencia del día
#
# LÓGICA:
#   1. Determinamos el BIAS del día usando el rango asiático:
#      - Si close actual > asia_high → sesgo alcista
#      - Si close actual < asia_low  → sesgo bajista
#      - Si dentro del rango          → sin sesgo (no operar)
#   2. Esperamos a que el mercado vuelva a la EMA21 en 5M durante NY session
#   3. Entramos en la dirección del bias con EMA9/21 confirmado
#   4. Stop: ATR × 1.2 bajo/sobre la EMA21
#   5. Target: RR 1.5
#
# OBJETIVO:
#   Complementar Estrategia A añadiendo 1-2 trades/semana en NY session
#   Sin solapar con A (A opera 07-13, B opera 13-20)

import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult


class USDJPYBacktesterB:
    # ── Indicadores ──
    EMA_FAST     = 9
    EMA_SLOW     = 21
    EMA_TREND    = 100    # bias de tendencia (mismo que Estrategia A)
    ADX_PERIOD   = 14
    ADX_MIN      = 12
    ADX_MAX      = 55
    ATR_PERIOD   = 14
    ATR_MIN      = 0.015  # ligeramente más permisivo que A (NY puede ser menos volátil)
    ATR_SL_MULT  = 1.2

    # ── Rango asiático (para determinar bias del día) ──
    ASIA_START   = 0
    ASIA_END     = 7

    # ── Sesión NY ──
    SESSION_START = 13   # 13:00 UTC (NY abre, London aún activo)
    SESSION_END   = 18   # 18:00 UTC — horas 18-19 mostraron WR <33% en diagnóstico

    # ── Gestión del trade ──
    RR_RATIO          = 1.5
    MAX_BARS_IN_TRADE = 30   # máximo 2.5h en trade (30 × 5M)
    MAX_TRADES_DAY    = 2    # hasta 2 entradas en NY session
    FRIDAY_CUTOFF     = 17   # no entrar en viernes después de 17 UTC
    MIN_BODY_RATIO    = 0.45 # vela de confirmación necesita cuerpo claro

    # ── Filtro pullback ──
    PULLBACK_ZONE_ATR  = 0.35  # zona estrecha: precio muy cerca de EMA21
    MIN_BARS_IN_TREND  = 5     # tendencia más establecida antes de entrar
    CONFIRM_BODY_RATIO = 0.35  # cuerpo mínimo de la vela de confirmación

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade: float = 0.005,
        rr_ratio: float = 1.5,
        symbol: str = "USDJPY",
        start_date: str | None = None,
        end_date:   str | None = None,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade  = risk_per_trade
        self.rr_ratio        = rr_ratio
        self.symbol          = symbol
        self.start_date      = start_date
        self.end_date        = end_date
        self.last_trades_detail = []

    # ─────────────────────────────────────────────
    # CARGA Y PREPARACIÓN DE DATOS
    # ─────────────────────────────────────────────

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(
            f"backtest/data/{self.symbol}_5M.csv",
            index_col=0,
            parse_dates=True,
        )
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()
        if self.start_date:
            df = df[df.index >= pd.Timestamp(self.start_date)]
        if self.end_date:
            df = df[df.index <= pd.Timestamp(self.end_date)]
        return df

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # EMAs
        df["ema9"]   = df["close"].ewm(span=self.EMA_FAST,  adjust=False).mean()
        df["ema21"]  = df["close"].ewm(span=self.EMA_SLOW,  adjust=False).mean()
        df["ema100"] = df["close"].ewm(span=self.EMA_TREND, adjust=False).mean()

        # ATR
        hl  = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"]  - df["close"].shift()).abs()
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.ATR_PERIOD).mean()

        # ADX
        up   = df["high"].diff()
        down = -df["low"].diff()
        pdm  = np.where((up > down) & (up > 0), up, 0.0)
        mdm  = np.where((down > up) & (down > 0), down, 0.0)
        atr_adx = tr.rolling(self.ADX_PERIOD).mean()
        pdi = 100 * pd.Series(pdm, index=df.index).rolling(self.ADX_PERIOD).mean() / (atr_adx + 1e-10)
        mdi = 100 * pd.Series(mdm, index=df.index).rolling(self.ADX_PERIOD).mean() / (atr_adx + 1e-10)
        dx  = 100 * (pdi - mdi).abs() / (pdi + mdi + 1e-10)
        df["adx"]      = dx.rolling(self.ADX_PERIOD).mean()
        df["plus_di"]  = pdi
        df["minus_di"] = mdi

        return df

    def _add_daily_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula rango asiático y bias del día."""
        df["hour"]    = df.index.hour
        df["date"]    = df.index.date
        df["weekday"] = df.index.weekday
        df["month"]   = df.index.month
        df["day"]     = df.index.day

        df["asia_high"] = np.nan
        df["asia_low"]  = np.nan

        for date, grp in df.groupby("date"):
            asia = grp[(grp["hour"] >= self.ASIA_START) & (grp["hour"] < self.ASIA_END)]
            if len(asia) == 0:
                continue
            df.loc[df["date"] == date, "asia_high"] = float(asia["high"].max())
            df.loc[df["date"] == date, "asia_low"]  = float(asia["low"].min())

        df["asia_range"] = df["asia_high"] - df["asia_low"]
        return df

    def prepare_dataframe(self) -> pd.DataFrame:
        df = self.load_data()
        df = self._add_indicators(df)
        df = self._add_daily_levels(df)
        cols = ["open","high","low","close","atr","adx","ema9","ema21","ema100",
                "asia_high","asia_low","asia_range","hour","date","weekday"]
        return df.dropna(subset=cols)

    # ─────────────────────────────────────────────
    # HELPERS DE SEÑAL
    # ─────────────────────────────────────────────

    @staticmethod
    def _body_ratio(row: pd.Series) -> float:
        rng = float(row["high"] - row["low"])
        if rng < 1e-10:
            return 0.0
        return abs(float(row["close"] - row["open"])) / rng

    def _daily_bias(self, row: pd.Series) -> str:
        """
        Determina el sesgo del día según posición respecto al rango asiático.
        Retorna 'BULL', 'BEAR' o 'NEUTRAL'.
        """
        close = float(row["close"])
        ah    = float(row["asia_high"])
        al    = float(row["asia_low"])
        if close > ah:
            return "BULL"
        if close < al:
            return "BEAR"
        return "NEUTRAL"

    def _is_pullback_to_ema21(self, df: pd.DataFrame, i: int) -> str:
        """
        Detecta si la vela actual es un pullback válido a la EMA21.
        Condiciones BUY:
          - EMA9 > EMA21 en las últimas MIN_BARS_IN_TREND velas
          - Precio toca zona EMA21 (dentro de PULLBACK_ZONE_ATR × ATR)
          - Precio cierra POR ENCIMA de EMA21 (rechazo)
        Retorna 'BUY', 'SELL' o 'NONE'.
        """
        if i < self.MIN_BARS_IN_TREND + 1:
            return "NONE"

        curr  = df.iloc[i]
        close = float(curr["close"])
        ema21 = float(curr["ema21"])
        atr_v = float(curr["atr"])

        near_ema21 = abs(close - ema21) < atr_v * self.PULLBACK_ZONE_ATR

        # Tendencia alcista establecida (últimas N velas EMA9 > EMA21)
        bull_trend = all(
            float(df.iloc[i - k]["ema9"]) > float(df.iloc[i - k]["ema21"])
            for k in range(1, self.MIN_BARS_IN_TREND + 1)
        )
        bear_trend = all(
            float(df.iloc[i - k]["ema9"]) < float(df.iloc[i - k]["ema21"])
            for k in range(1, self.MIN_BARS_IN_TREND + 1)
        )

        if bull_trend and near_ema21 and close > ema21:
            return "BUY"
        if bear_trend and near_ema21 and close < ema21:
            return "SELL"
        return "NONE"

    # ─────────────────────────────────────────────
    # EJECUCIÓN DEL BACKTEST
    # ─────────────────────────────────────────────

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()
        print(f"{self.symbol} B: {len(df)} velas | {df.index.min()} → {df.index.max()}")

        balance       = self.initial_balance
        equity_curve  = [balance]
        trades        = []
        trades_detail = []
        trades_by_day = {}
        exit_stats    = {"tp": 0, "sl": 0, "timeout": 0}

        for i in range(max(120, self.MIN_BARS_IN_TREND + 2), len(df) - 5):
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

            # ── Límite de trades por día ──
            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            # ── Filtros de volatilidad y tendencia ──
            curr_atr = float(row["atr"])
            if curr_atr < self.ATR_MIN:
                continue
            curr_adx = float(row["adx"])
            if curr_adx < self.ADX_MIN or curr_adx > self.ADX_MAX:
                continue
            if float(row["asia_range"]) <= 0:
                continue

            # ── Bias del día ──
            bias = self._daily_bias(row)
            if bias == "NEUTRAL":
                continue

            # ── Señal de pullback (barra i = toca EMA21) ──
            pullback_dir = self._is_pullback_to_ema21(df, i)
            if pullback_dir == "NONE":
                continue

            # La dirección del pullback debe coincidir con el bias del día
            if (bias == "BULL" and pullback_dir != "BUY") or \
               (bias == "BEAR" and pullback_dir != "SELL"):
                continue

            # ── Vela de confirmación (barra i+1 = confirma el rebote) ──
            # Sin look-ahead real: en live trading esperaríamos al cierre de i+1
            if i + 1 >= len(df):
                continue
            conf = df.iloc[i + 1]
            conf_close = float(conf["close"])
            conf_open  = float(conf["open"])
            conf_ema21 = float(conf["ema21"])
            conf_ema9  = float(conf["ema9"])

            conf_body = self._body_ratio(conf)
            if conf_body < self.CONFIRM_BODY_RATIO:
                continue  # doji o vela sin convicción

            if pullback_dir == "BUY":
                # Confirmación: cierra alcista y por encima de EMA21
                if not (conf_close > conf_open and conf_close > conf_ema21):
                    continue
            else:
                # Confirmación: cierra bajista y por debajo de EMA21
                if not (conf_close < conf_open and conf_close < conf_ema21):
                    continue

            # ── Construcción del trade — entramos al cierre de la vela de confirmación ──
            entry = conf_close
            if pullback_dir == "BUY":
                sl            = conf_ema21 - curr_atr * self.ATR_SL_MULT
                risk_distance = entry - sl
                tp            = entry + risk_distance * self.rr_ratio
            else:
                sl            = conf_ema21 + curr_atr * self.ATR_SL_MULT
                risk_distance = sl - entry
                tp            = entry - risk_distance * self.rr_ratio

            if risk_distance <= 0:
                continue

            # ── Gestión del trade (barra a barra) ──
            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt    = balance * self.risk_per_trade
            won         = False
            exit_reason = "timeout"
            entry_bar   = i + 1   # entramos al cierre de la vela de confirmación
            exit_time   = df.index[min(entry_bar + self.MAX_BARS_IN_TRADE, len(df) - 1)]
            exit_price  = entry
            bars_held   = 0

            for j in range(entry_bar + 1, min(entry_bar + 1 + self.MAX_BARS_IN_TRADE, len(df))):
                fh = float(df.iloc[j]["high"])
                fl = float(df.iloc[j]["low"])
                bars_held = j - i

                if pullback_dir == "BUY":
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
                timeout_idx = min(entry_bar + self.MAX_BARS_IN_TRADE, len(df) - 1)
                exit_time   = df.index[timeout_idx]
                exit_price  = float(df.iloc[timeout_idx]["close"])
                # P&L por timeout: precio real
                pnl = (exit_price - entry if pullback_dir == "BUY"
                       else entry - exit_price) / risk_distance * risk_amt
            elif won:
                pnl = risk_amt * self.rr_ratio
            else:
                pnl = -risk_amt

            balance_before = balance
            balance       += pnl
            equity_curve.append(balance)

            trades.append({"pnl": pnl, "won": won, "signal": pullback_dir,
                           "exit_reason": exit_reason})
            trades_detail.append({
                "entry_time":    df.index[i],
                "exit_time":     exit_time,
                "signal":        pullback_dir,
                "bias":          bias,
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

        pnls  = np.array([t["pnl"] for t in trades], dtype=float)
        wins  = [t for t in trades if t["pnl"] > 0]
        losses= [t for t in trades if t["pnl"] < 0]
        eq    = np.array(equity_curve, dtype=float)

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
