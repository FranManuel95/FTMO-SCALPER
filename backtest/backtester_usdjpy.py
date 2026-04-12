import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult


class USDJPYBacktester:
    EMA_FAST = 20
    EMA_SLOW = 100
    ADX_PERIOD = 14
    ADX_MIN = 12
    ADX_MAX = 50

    ATR_PERIOD = 14
    ATR_MIN = 0.020
    ATR_SL_MULT = 1.0

    ASIA_START = 0
    ASIA_END = 7
    BUFFER_PIPS = 0.04

    SESSION_START = 7
    SESSION_END = 16
    MAX_TRADES_DAY = 1
    MAX_BARS_IN_TRADE = 42
    FRIDAY_CUTOFF_HOUR = 14

    MIN_BODY_RATIO = 0.50
    RANGE_ATR_CAP = 5.0
    BREAK_EVEN_R = 999.0

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade: float = 0.005,
        rr_ratio: float = 1.4,
        symbol: str = "USDJPY",
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.rr_ratio = rr_ratio
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.last_trades_detail = []

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(
            f"backtest/data/{self.symbol}_5M.csv",
            index_col=0,
            parse_dates=True,
        )
        df.columns = [c.lower() for c in df.columns]
        df = df.sort_index()

        if self.start_date is not None:
            df = df[df.index >= pd.Timestamp(self.start_date)]
        if self.end_date is not None:
            df = df[df.index <= pd.Timestamp(self.end_date)]

        return df

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

        plus_di = (
            100
            * pd.Series(plus_dm, index=df.index).rolling(self.ADX_PERIOD).mean()
            / (atr + 1e-10)
        )
        minus_di = (
            100
            * pd.Series(minus_dm, index=df.index).rolling(self.ADX_PERIOD).mean()
            / (atr + 1e-10)
        )

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        df["adx"] = dx.rolling(self.ADX_PERIOD).mean()
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di
        return df

    def _add_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        if "tick_volume" in df.columns:
            vol = df["tick_volume"].replace(0, 1)
        elif "volume" in df.columns:
            vol = df["volume"].replace(0, 1)
        else:
            vol = pd.Series(1.0, index=df.index)

        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        date_key = df.index.date
        pv = typical_price * vol
        df["vwap"] = pv.groupby(date_key).cumsum() / vol.groupby(date_key).cumsum()
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
                (group["hour"] >= self.ASIA_START) &
                (group["hour"] < self.ASIA_END)
            ]
            if len(asia) == 0:
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

    def prepare_dataframe(self) -> pd.DataFrame:
        df = self.load_data()
        df = self._add_atr(df)
        df = self._add_adx(df)
        df["ema_fast"] = df["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()
        df = self._add_vwap(df)
        df = self._prepare_intraday_levels(df)

        cols = [
            "open", "high", "low", "close",
            "atr", "adx", "ema_fast", "ema_slow",
            "vwap", "asia_high", "asia_low", "asia_range",
            "hour", "day", "month", "date", "weekday",
        ]
        df = df.dropna(subset=cols)
        return df

    def run(self) -> BacktestResult:
        df = self.prepare_dataframe()
        print(
            f"{self.symbol} 5M: {len(df)} velas"
            + (
                f" | Rango: {df.index.min()} -> {df.index.max()}"
                if len(df) else ""
            )
        )

        balance = self.initial_balance
        equity_curve = [balance]
        trades = []
        trades_by_day = {}
        trades_detail = []
        exit_stats = {"tp": 0, "sl": 0, "breakeven": 0, "timeout": 0}

        for i in range(120, len(df) - 5):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if row["hour"] < self.SESSION_START or row["hour"] >= self.SESSION_END:
                continue
            if row["weekday"] >= 5:
                continue
            if row["weekday"] == 4 and row["hour"] >= self.FRIDAY_CUTOFF_HOUR:
                continue

            is_xmas = (
                (row["month"] == 12 and row["day"] >= 20)
                or (row["month"] == 1 and row["day"] <= 3)
            )
            if is_xmas:
                continue

            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            curr_atr = float(row["atr"])
            if curr_atr < self.ATR_MIN:
                continue

            adx = float(row["adx"])
            if adx < self.ADX_MIN or adx > self.ADX_MAX:
                continue

            asia_range = float(row["asia_range"])
            if asia_range <= 0:
                continue
            if asia_range > curr_atr * self.RANGE_ATR_CAP:
                continue

            body_ratio = self._body_ratio(row)
            if body_ratio < self.MIN_BODY_RATIO:
                continue

            ema_bull = float(row["ema_fast"]) > float(row["ema_slow"])
            ema_bear = float(row["ema_fast"]) < float(row["ema_slow"])

            asia_high = float(row["asia_high"])
            asia_low = float(row["asia_low"])
            prev_close = float(prev["close"])
            curr_close = float(row["close"])
            curr_high = float(row["high"])
            curr_low = float(row["low"])

            signal_val = None
            entry = curr_close
            sl = None
            tp = None
            risk_distance = None

            breakout_up = prev_close <= asia_high and curr_close > (asia_high + self.BUFFER_PIPS)
            breakout_dn = prev_close >= asia_low and curr_close < (asia_low - self.BUFFER_PIPS)

            if breakout_up and ema_bull:
                signal_val = "BUY"
                sl = min(curr_low, asia_high) - self.BUFFER_PIPS
                risk_distance = entry - sl
                tp = entry + risk_distance * self.rr_ratio

            elif breakout_dn and ema_bear:
                signal_val = "SELL"
                sl = max(curr_high, asia_low) + self.BUFFER_PIPS
                risk_distance = sl - entry
                tp = entry - risk_distance * self.rr_ratio

            if not signal_val or risk_distance is None or risk_distance <= 0:
                continue

            trades_by_day[date] = trades_by_day.get(date, 0) + 1
            risk_amt = balance * self.risk_per_trade

            won = False
            exit_reason = "timeout"
            moved_be = False
            be_price = entry
            exit_time = df.index[min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)]
            exit_price = curr_close
            bars_held = 0

            for j in range(i + 1, min(i + 1 + self.MAX_BARS_IN_TRADE, len(df))):
                fh = float(df.iloc[j]["high"])
                fl = float(df.iloc[j]["low"])
                bars_held = j - i

                if signal_val == "BUY":
                    if not moved_be and fh >= entry + risk_distance * self.BREAK_EVEN_R:
                        sl = be_price
                        moved_be = True

                    if fh >= tp:
                        won = True
                        exit_reason = "tp"
                        exit_time = df.index[j]
                        exit_price = tp
                        break

                    if fl <= sl:
                        exit_reason = "breakeven" if moved_be and abs(sl - be_price) < 1e-10 else "sl"
                        exit_time = df.index[j]
                        exit_price = sl
                        break
                else:
                    if not moved_be and fl <= entry - risk_distance * self.BREAK_EVEN_R:
                        sl = be_price
                        moved_be = True

                    if fl <= tp:
                        won = True
                        exit_reason = "tp"
                        exit_time = df.index[j]
                        exit_price = tp
                        break

                    if fh >= sl:
                        exit_reason = "breakeven" if moved_be and abs(sl - be_price) < 1e-10 else "sl"
                        exit_time = df.index[j]
                        exit_price = sl
                        break

            if exit_reason == "timeout":
                timeout_idx = min(i + self.MAX_BARS_IN_TRADE, len(df) - 1)
                exit_time = df.index[timeout_idx]
                exit_price = float(df.iloc[timeout_idx]["close"])

            if exit_reason == "breakeven":
                pnl = 0.0
            elif won:
                pnl = risk_amt * self.rr_ratio
            else:
                pnl = -risk_amt

            balance_before = balance
            balance += pnl
            equity_curve.append(balance)

            trades.append({
                "pnl": pnl,
                "won": won,
                "signal": signal_val,
                "exit_reason": exit_reason,
            })

            trades_detail.append({
                "entry_time": df.index[i],
                "exit_time": exit_time,
                "signal": signal_val,
                "entry_price": round(entry, 5),
                "sl_price": round(sl, 5),
                "tp_price": round(tp, 5),
                "exit_price": round(float(exit_price), 5),
                "risk_distance": round(float(risk_distance), 5),
                "bars_held": int(bars_held),
                "exit_reason": exit_reason,
                "won": bool(won),
                "balance_before": round(float(balance_before), 2),
                "pnl": round(float(pnl), 2),
                "balance_after": round(float(balance), 2),
            })

            exit_stats[exit_reason] += 1

        self.last_trades_detail = trades_detail
        result = self._compute_metrics(trades, equity_curve)
        result.extra_stats = exit_stats
        return result

    def _compute_metrics(self, trades, equity_curve):
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
                equity_curve=list(equity_curve),
            )

        pnls = np.array([t["pnl"] for t in trades], dtype=float)
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] < 0]
        eq = np.array(equity_curve, dtype=float)

        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak
        max_dd = float(np.max(dd))

        rets = np.diff(eq) / eq[:-1]
        sharpe = 0.0
        sortino = 0.0

        if len(rets) > 1:
            sharpe = (float(np.mean(rets)) / (float(np.std(rets)) + 1e-10)) * np.sqrt(252)
            neg_rets = rets[rets < 0]
            if len(neg_rets) > 0:
                sortino = (float(np.mean(rets)) / (float(np.std(neg_rets)) + 1e-10)) * np.sqrt(252)

        gp = sum(t["pnl"] for t in wins)
        gl = abs(sum(t["pnl"] for t in losses))
        pf = gp / (gl + 1e-10)

        return BacktestResult(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / len(trades),
            profit_factor=round(pf, 3),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            max_drawdown=round(max_dd, 4),
            total_return=round((eq[-1] - eq[0]) / eq[0], 4),
            avg_win=round(gp / (len(wins) + 1e-10), 2),
            avg_loss=round(gl / (len(losses) + 1e-10), 2),
            expectancy=round(float(np.mean(pnls)), 2),
            equity_curve=list(eq),
        )