import os
import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult


class EURJPYBacktester:
    """
    Backtester EURJPY M5:
    - Breakout del rango asiático -> sesión europea
    - Confirmación por EMA trend filter + ADX regime
    - Filtro de body ratio mínimo
    - Entrada en la vela siguiente a la señal
    - Spread + slippage
    - Resolución conservadora de velas ambiguas
    - Timeout real al precio de cierre
    - Registro detallado de trades
    - Stop híbrido: estructura + ATR
    """

    EMA_FAST = 20
    EMA_SLOW = 100

    ADX_PERIOD = 14
    ATR_PERIOD = 14

    MAX_TRADES_DAY = 1
    MAX_HOLD_BARS = 24

    ASIA_START = 0
    ASIA_END = 7

    SESSION_START = 7
    SESSION_END = 13

    FRIDAY_CUTOFF_HOUR = 12

    SPREAD = 0.015
    SLIPPAGE = 0.003

    FILTER_XMAS = True
    USE_WORST_CASE_INTRABAR = True

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade: float = 0.005,
        rr_ratio: float = 1.4,
        atr_sl_mult: float = 1.2,
        symbol: str = "EURJPY",
        export_trades: bool = True,
        session_start: int = 7,
        session_end: int = 13,
        asia_start: int = 0,
        asia_end: int = 7,
        adx_min: float = 18,
        adx_max: float = 50,
        atr_min: float = 0.08,
        breakout_buffer_atr: float = 0.05,
        min_body_ratio: float = 0.35,
        range_atr_min: float = 0.4,
        range_atr_cap: float = 4.0,
        trade_mode: str = "BOTH",
        friday_cutoff_hour: int = 12,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.rr_ratio = rr_ratio
        self.atr_sl_mult = atr_sl_mult
        self.symbol = symbol
        self.export_trades = export_trades

        self.session_start = session_start
        self.session_end = session_end
        self.asia_start = asia_start
        self.asia_end = asia_end

        self.adx_min = adx_min
        self.adx_max = adx_max
        self.atr_min = atr_min

        self.breakout_buffer_atr = breakout_buffer_atr
        self.min_body_ratio = min_body_ratio
        self.range_atr_min = range_atr_min
        self.range_atr_cap = range_atr_cap

        self.trade_mode = trade_mode.upper()
        self.friday_cutoff_hour = friday_cutoff_hour

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(
            f"backtest/data/{self.symbol}_5M.csv",
            index_col=0,
            parse_dates=True,
        )
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        hl = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.ATR_PERIOD).mean()
        return df

    def _add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        high = df["high"]
        low = df["low"]
        close = df["close"]

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        hl = high - low
        hcp = (high - close.shift()).abs()
        lcp = (low - close.shift()).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        atr = tr.rolling(self.ADX_PERIOD).mean()

        plus_dm = pd.Series(plus_dm, index=df.index)
        minus_dm = pd.Series(minus_dm, index=df.index)

        plus_di = 100 * plus_dm.rolling(self.ADX_PERIOD).mean() / (atr + 1e-10)
        minus_di = 100 * minus_dm.rolling(self.ADX_PERIOD).mean() / (atr + 1e-10)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        adx = dx.rolling(self.ADX_PERIOD).mean()

        df["adx"] = adx
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di
        return df

    def _prepare_intraday_levels(self, df: pd.DataFrame) -> pd.DataFrame:
        df["hour"] = df.index.hour
        df["day"] = df.index.day
        df["month"] = df.index.month
        df["date"] = df.index.date
        df["weekday"] = df.index.weekday

        df["asia_high"] = np.nan
        df["asia_low"] = np.nan

        for date, group in df.groupby("date"):
            asia = group[
                (group["hour"] >= self.asia_start) &
                (group["hour"] < self.asia_end)
            ]

            if asia.empty:
                continue

            df.loc[df["date"] == date, "asia_high"] = float(asia["high"].max())
            df.loc[df["date"] == date, "asia_low"] = float(asia["low"].min())

        df["asia_range"] = df["asia_high"] - df["asia_low"]
        return df

    @staticmethod
    def _body_ratio(row: pd.Series) -> float:
        candle_range = float(row["high"] - row["low"])
        if candle_range <= 1e-10:
            return 0.0
        body = abs(float(row["close"] - row["open"]))
        return body / candle_range

    def _is_xmas_period(self, row: pd.Series) -> bool:
        return (
            (row["month"] == 12 and row["day"] >= 20) or
            (row["month"] == 1 and row["day"] <= 3)
        )

    def _compute_daily_returns_from_trades(self, trades_df: pd.DataFrame) -> np.ndarray:
        if trades_df.empty:
            return np.array([])

        daily_pnl = trades_df.groupby("exit_date")["pnl"].sum().sort_index()

        balance = self.initial_balance
        equity = []
        for pnl in daily_pnl.values:
            balance += pnl
            equity.append(balance)

        equity = np.array([self.initial_balance] + equity, dtype=float)
        if len(equity) < 2:
            return np.array([])

        return np.diff(equity) / equity[:-1]

    def _export_trades_csv(self, trades_df: pd.DataFrame):
        os.makedirs("backtest/results", exist_ok=True)
        path = f"backtest/results/{self.symbol.lower()}_breakout_trades.csv"
        trades_df.to_csv(path, index=False)
        print(f"Trades guardados en: {path}")

    def prepare_dataframe(self) -> pd.DataFrame:
        df = self.load_data()
        df = self._add_atr(df)
        df = self._add_adx(df)

        df["ema_fast"] = df["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()

        df = self._prepare_intraday_levels(df)

        cols = [
            "open", "high", "low", "close",
            "atr", "adx", "ema_fast", "ema_slow",
            "asia_high", "asia_low", "asia_range",
            "hour", "day", "month", "date", "weekday",
        ]
        df = df.dropna(subset=cols).copy()
        return df

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()

        print(
            f"{self.symbol} 5M: {len(df)} velas | "
            f"Mode: {self.trade_mode} | "
            f"Session: {self.session_start}-{self.session_end} | "
            f"Asia: {self.asia_start}-{self.asia_end} | "
            f"ADX: {self.adx_min}-{self.adx_max} | "
            f"ATR_MIN: {self.atr_min} | "
            f"RR: {self.rr_ratio} | SLxATR: {self.atr_sl_mult}"
        )

        balance = self.initial_balance
        equity_curve = [balance]
        trades = []
        trades_by_day = {}

        for i in range(120, len(df) - self.MAX_HOLD_BARS - 2):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if row["hour"] < self.session_start or row["hour"] >= self.session_end:
                continue
            if row["weekday"] >= 5:
                continue
            if row["weekday"] == 4 and row["hour"] >= self.friday_cutoff_hour:
                continue
            if self.FILTER_XMAS and self._is_xmas_period(row):
                continue

            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            curr_atr = float(row["atr"])
            if curr_atr < self.atr_min:
                continue

            adx = float(row["adx"])
            if adx < self.adx_min or adx > self.adx_max:
                continue

            asia_high = float(row["asia_high"])
            asia_low = float(row["asia_low"])
            asia_range = float(row["asia_range"])

            if asia_range <= 0:
                continue
            if asia_range < curr_atr * self.range_atr_min:
                continue
            if asia_range > curr_atr * self.range_atr_cap:
                continue

            body_ratio = self._body_ratio(row)
            if body_ratio < self.min_body_ratio:
                continue

            ema_bull = float(row["ema_fast"]) > float(row["ema_slow"])
            ema_bear = float(row["ema_fast"]) < float(row["ema_slow"])

            curr_close = float(row["close"])
            curr_high = float(row["high"])
            curr_low = float(row["low"])

            buffer_val = curr_atr * self.breakout_buffer_atr

            breakout_up = (curr_high > (asia_high + buffer_val)) and (curr_close > asia_high)
            breakout_dn = (curr_low < (asia_low - buffer_val)) and (curr_close < asia_low)

            signal_val = None
            signal_time = df.index[i]

            if breakout_up and ema_bull:
                signal_val = "BUY"
            elif breakout_dn and ema_bear:
                signal_val = "SELL"

            if not signal_val:
                continue
            if self.trade_mode == "BUY_ONLY" and signal_val != "BUY":
                continue
            if self.trade_mode == "SELL_ONLY" and signal_val != "SELL":
                continue

            entry_row = df.iloc[i + 1]
            entry_time = df.index[i + 1]
            raw_entry = float(entry_row["open"])

            if signal_val == "BUY":
                entry = raw_entry + self.SPREAD / 2 + self.SLIPPAGE

                structural_sl = min(curr_low, asia_high) - curr_atr * 0.10
                atr_sl = entry - curr_atr * self.atr_sl_mult
                sl = min(structural_sl, atr_sl)

                risk_per_unit = entry - sl
                tp = entry + risk_per_unit * self.rr_ratio
            else:
                entry = raw_entry - self.SPREAD / 2 - self.SLIPPAGE

                structural_sl = max(curr_high, asia_low) + curr_atr * 0.10
                atr_sl = entry + curr_atr * self.atr_sl_mult
                sl = max(structural_sl, atr_sl)

                risk_per_unit = sl - entry
                tp = entry - risk_per_unit * self.rr_ratio

            if risk_per_unit <= 0:
                continue

            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt = balance * self.risk_per_trade

            exit_price = None
            exit_time = None
            exit_reason = None
            won = None
            bars_held = 0

            last_j = min(i + 1 + self.MAX_HOLD_BARS, len(df) - 1)

            for j in range(i + 1, last_j + 1):
                fut = df.iloc[j]
                fh = float(fut["high"])
                fl = float(fut["low"])
                bars_held += 1

                if signal_val == "BUY":
                    hit_tp = fh >= tp
                    hit_sl = fl <= sl

                    if hit_tp and hit_sl:
                        exit_price = sl if self.USE_WORST_CASE_INTRABAR else tp
                        exit_reason = "ambiguous_sl" if self.USE_WORST_CASE_INTRABAR else "ambiguous_tp"
                        won = not self.USE_WORST_CASE_INTRABAR
                        exit_time = df.index[j]
                        break

                    if hit_sl:
                        exit_price = sl
                        exit_reason = "sl"
                        won = False
                        exit_time = df.index[j]
                        break

                    if hit_tp:
                        exit_price = tp
                        exit_reason = "tp"
                        won = True
                        exit_time = df.index[j]
                        break

                else:
                    hit_tp = fl <= tp
                    hit_sl = fh >= sl

                    if hit_tp and hit_sl:
                        exit_price = sl if self.USE_WORST_CASE_INTRABAR else tp
                        exit_reason = "ambiguous_sl" if self.USE_WORST_CASE_INTRABAR else "ambiguous_tp"
                        won = not self.USE_WORST_CASE_INTRABAR
                        exit_time = df.index[j]
                        break

                    if hit_sl:
                        exit_price = sl
                        exit_reason = "sl"
                        won = False
                        exit_time = df.index[j]
                        break

                    if hit_tp:
                        exit_price = tp
                        exit_reason = "tp"
                        won = True
                        exit_time = df.index[j]
                        break

            if exit_price is None:
                timeout_row = df.iloc[last_j]
                raw_exit = float(timeout_row["close"])

                if signal_val == "BUY":
                    exit_price = raw_exit - self.SPREAD / 2 - self.SLIPPAGE
                    pnl_r = (exit_price - entry) / risk_per_unit
                else:
                    exit_price = raw_exit + self.SPREAD / 2 + self.SLIPPAGE
                    pnl_r = (entry - exit_price) / risk_per_unit

                exit_time = df.index[last_j]
                exit_reason = "timeout"
                pnl = risk_amt * pnl_r
                won = pnl > 0
            else:
                if signal_val == "BUY":
                    pnl_r = (exit_price - entry) / risk_per_unit
                else:
                    pnl_r = (entry - exit_price) / risk_per_unit

                pnl = risk_amt * pnl_r

            balance += pnl
            equity_curve.append(balance)

            trades.append({
                "signal_time": signal_time,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_date": pd.to_datetime(entry_time).date(),
                "exit_date": pd.to_datetime(exit_time).date(),
                "side": signal_val,
                "entry": round(entry, 5),
                "exit": round(float(exit_price), 5),
                "sl": round(float(sl), 5),
                "tp": round(float(tp), 5),
                "atr": round(curr_atr, 5),
                "adx": round(adx, 4),
                "asia_high": round(asia_high, 5),
                "asia_low": round(asia_low, 5),
                "asia_range": round(asia_range, 5),
                "ema_fast": round(float(row["ema_fast"]), 5),
                "ema_slow": round(float(row["ema_slow"]), 5),
                "signal_hour": int(pd.to_datetime(signal_time).hour),
                "entry_hour": int(pd.to_datetime(entry_time).hour),
                "weekday": int(row["weekday"]),
                "month": int(row["month"]),
                "body_ratio": round(body_ratio, 4),
                "risk_amt": round(risk_amt, 2),
                "risk_per_unit": round(risk_per_unit, 5),
                "pnl": round(float(pnl), 2),
                "pnl_r": round(float(pnl_r), 4),
                "won": bool(won),
                "exit_reason": exit_reason,
                "bars_held": int(bars_held),
                "balance_after": round(balance, 2),
            })

        return self._compute_metrics(trades, equity_curve)

    def _compute_metrics(self, trades, equity_curve):
        if not trades:
            raise ValueError("Sin trades.")

        trades_df = pd.DataFrame(trades)

        if self.export_trades:
            self._export_trades_csv(trades_df)

        pnls = trades_df["pnl"].values
        wins_df = trades_df[trades_df["pnl"] > 0]
        losses_df = trades_df[trades_df["pnl"] <= 0]

        eq = np.array(equity_curve, dtype=float)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak
        max_dd = float(np.max(dd))

        daily_ret = self._compute_daily_returns_from_trades(trades_df)

        if len(daily_ret) > 1 and np.std(daily_ret) > 1e-10:
            sharpe = (float(np.mean(daily_ret)) / (float(np.std(daily_ret)) + 1e-10)) * np.sqrt(252)
        else:
            sharpe = 0.0

        neg_ret = daily_ret[daily_ret < 0]
        if len(neg_ret) > 1 and np.std(neg_ret) > 1e-10:
            sortino = (float(np.mean(daily_ret)) / (float(np.std(neg_ret)) + 1e-10)) * np.sqrt(252)
        else:
            sortino = 0.0

        gp = float(wins_df["pnl"].sum())
        gl = abs(float(losses_df["pnl"].sum()))
        pf = gp / (gl + 1e-10)

        print("\n=== EXIT REASONS ===")
        print(trades_df["exit_reason"].value_counts().to_string())

        monthly = (
            trades_df.groupby("month")
            .agg(
                trades=("pnl", "count"),
                wins=("won", "sum"),
                pnl=("pnl", "sum"),
                avg_pnl=("pnl", "mean"),
                avg_r=("pnl_r", "mean"),
                tp=("exit_reason", lambda s: int((s == "tp").sum())),
                sl=("exit_reason", lambda s: int((s == "sl").sum())),
                timeout=("exit_reason", lambda s: int((s == "timeout").sum())),
                ambiguous=("exit_reason", lambda s: int(s.astype(str).str.contains("ambiguous").sum())),
            )
            .reset_index()
        )
        monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(2)

        print("\n=== RESUMEN MENSUAL ===")
        print(monthly.to_string(index=False))

        return BacktestResult(
            total_trades=len(trades_df),
            winning_trades=int((trades_df["pnl"] > 0).sum()),
            losing_trades=int((trades_df["pnl"] <= 0).sum()),
            win_rate=float((trades_df["pnl"] > 0).mean()),
            profit_factor=round(pf, 3),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            max_drawdown=round(max_dd, 4),
            total_return=round((eq[-1] - eq[0]) / eq[0], 4),
            avg_win=round(float(wins_df["pnl"].mean()) if not wins_df.empty else 0.0, 2),
            avg_loss=round(abs(float(losses_df["pnl"].mean())) if not losses_df.empty else 0.0, 2),
            expectancy=round(float(np.mean(pnls)), 2),
            equity_curve=list(eq),
        )