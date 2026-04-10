# # backtest/backtester_gbp.py — SuperTrend + Regime Filter para GBP/USD

# import pandas as pd
# import numpy as np
# from backtest.backtester import BacktestResult

# class GBPBacktester:

#     ST_PERIOD      = 10
#     ST_MULT        = 3.0
#     ADX_PERIOD     = 14
#     ADX_MIN        = 20
#     ADX_MAX        = 60
#     EMA_FAST       = 50
#     EMA_SLOW       = 200
#     ATR_PERIOD     = 14
#     ATR_SL_MULT    = 1.2
#     RR_RATIO       = 1.4
#     ATR_MIN        = 0.0004
#     SESSION_START  = 7
#     SESSION_END    = 17
#     MAX_TRADES_DAY = 1

#     def __init__(self, initial_balance: float = 10000,
#                  risk_per_trade: float = 0.005,
#                  rr_ratio: float = 1.6,
#                  symbol: str = "GBPUSD"):
#         self.initial_balance = initial_balance
#         self.risk_per_trade  = risk_per_trade
#         self.rr_ratio        = rr_ratio
#         self.symbol          = symbol

#     def load_data(self) -> pd.DataFrame:
#         df = pd.read_csv(f"backtest/data/{self.symbol}_5M.csv",                         index_col=0, parse_dates=True)
#         df.columns = [c.lower() for c in df.columns]
#         return df.sort_index()

#     def _add_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
#         high  = df['high'].values
#         low   = df['low'].values
#         close = df['close'].values
#         n     = len(df)

#         tr = np.zeros(n)
#         for i in range(1, n):
#             tr[i] = max(high[i] - low[i],
#                         abs(high[i] - close[i-1]),
#                         abs(low[i]  - close[i-1]))

#         atr = np.zeros(n)
#         for i in range(self.ST_PERIOD, n):
#             atr[i] = np.mean(tr[i-self.ST_PERIOD+1:i+1])

#         hl2         = (high + low) / 2
#         upper_basic = hl2 + self.ST_MULT * atr
#         lower_basic = hl2 - self.ST_MULT * atr

#         upper      = upper_basic.copy()
#         lower      = lower_basic.copy()
#         direction  = np.ones(n)
#         supertrend = np.zeros(n)

#         for i in range(1, n):
#             if upper_basic[i] < upper[i-1] or close[i-1] > upper[i-1]:
#                 upper[i] = upper_basic[i]
#             else:
#                 upper[i] = upper[i-1]

#             if lower_basic[i] > lower[i-1] or close[i-1] < lower[i-1]:
#                 lower[i] = lower_basic[i]
#             else:
#                 lower[i] = lower[i-1]

#             if direction[i-1] == -1 and close[i] > upper[i]:
#                 direction[i] = 1
#             elif direction[i-1] == 1 and close[i] < lower[i]:
#                 direction[i] = -1
#             else:
#                 direction[i] = direction[i-1]

#             supertrend[i] = lower[i] if direction[i] == 1 else upper[i]

#         supertrend[:self.ST_PERIOD] = np.nan

#         df['supertrend']   = supertrend
#         df['st_direction'] = direction
#         return df

#     def _add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
#         high  = df['high']
#         low   = df['low']
#         close = df['close']
#         plus_dm  = high.diff().clip(lower=0)
#         minus_dm = (-low.diff()).clip(lower=0)
#         hl   = high - low
#         hcp  = (high - close.shift()).abs()
#         lcp  = (low  - close.shift()).abs()
#         tr   = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
#         atr  = tr.rolling(self.ADX_PERIOD).mean()
#         plus_di  = 100 * plus_dm.rolling(self.ADX_PERIOD).mean()  / (atr + 1e-10)
#         minus_di = 100 * minus_dm.rolling(self.ADX_PERIOD).mean() / (atr + 1e-10)
#         dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
#         df['adx']      = dx.rolling(self.ADX_PERIOD).mean()
#         df['plus_di']  = plus_di
#         df['minus_di'] = minus_di
#         return df

#     def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
#         hl  = df['high'] - df['low']
#         hcp = (df['high'] - df['close'].shift()).abs()
#         lcp = (df['low']  - df['close'].shift()).abs()
#         df['atr'] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(self.ATR_PERIOD).mean()
#         return df

#     def run(self) -> BacktestResult:
#         df = self.load_data()
#         df = self._add_supertrend(df)
#         df = self._add_adx(df)
#         df = self._add_atr(df)

#         df['ema50']   = df['close'].ewm(span=self.EMA_FAST, adjust=False).mean()
#         df['ema200']  = df['close'].ewm(span=self.EMA_SLOW, adjust=False).mean()
#         df['hour']    = df.index.hour
#         df['day']     = df.index.day
#         df['month']   = df.index.month
#         df['date']    = df.index.date
#         df['weekday'] = df.index.weekday

#         cols = ['supertrend', 'st_direction', 'adx', 'atr', 'ema50', 'ema200']
#         df = df.dropna(subset=cols)
#         print(f"{self.symbol} 5M: {len(df)} velas")

#         balance       = self.initial_balance
#         equity_curve  = [balance]
#         trades        = []
#         trades_by_day = {}

#         for i in range(220, len(df) - 10):
#             row  = df.iloc[i]
#             prev = df.iloc[i-1]

#             if row['hour'] < self.SESSION_START or row['hour'] >= self.SESSION_END:
#                 continue
#             if row['weekday'] >= 5:
#                 continue

#             # Filtro navideño: 20 Dic - 3 Ene
#             is_xmas = (row['month'] == 12 and row['day'] >= 20) or \
#                       (row['month'] == 1  and row['day'] <= 3)
#             if is_xmas:
#                 continue

#             date = row['date']
#             if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
#                 continue

#             curr_atr   = float(row['atr'])
#             curr_close = float(row['close'])

#             if curr_atr < self.ATR_MIN:
#                 continue

#             adx = float(row['adx'])
#             if adx < self.ADX_MIN or adx > self.ADX_MAX:
#                 continue

#             trend_bull = float(row['ema50']) > float(row['ema200'])
#             trend_bear = float(row['ema50']) < float(row['ema200'])
#             curr_dir   = float(row['st_direction'])
#             prev_dir   = float(prev['st_direction'])

#             signal_val = None
#             entry = curr_close

#             if prev_dir == -1 and curr_dir == 1 and trend_bull:
#                 signal_val = 'BUY'
#                 sl = entry - curr_atr * self.ATR_SL_MULT
#                 tp = entry + curr_atr * self.ATR_SL_MULT * self.rr_ratio

#             elif prev_dir == 1 and curr_dir == -1 and trend_bear:
#                 signal_val = 'SELL'
#                 sl = entry + curr_atr * self.ATR_SL_MULT
#                 tp = entry - curr_atr * self.ATR_SL_MULT * self.rr_ratio

#             if not signal_val:
#                 continue

#             trades_by_day[date] = trades_by_day.get(date, 0) + 1
#             risk_amt = balance * self.risk_per_trade
#             won = False

#             for j in range(i+1, min(i+30, len(df))):
#                 fh = float(df.iloc[j]['high'])
#                 fl = float(df.iloc[j]['low'])
#                 if signal_val == 'BUY':
#                     if fh >= tp: won = True;  break
#                     if fl <= sl: won = False; break
#                 else:
#                     if fl <= tp: won = True;  break
#                     if fh >= sl: won = False; break

#             pnl = risk_amt * self.rr_ratio if won else -risk_amt
#             balance += pnl
#             equity_curve.append(balance)
#             trades.append({'pnl': pnl, 'won': won})

#         return self._compute_metrics(trades, equity_curve)

#     def _compute_metrics(self, trades, equity_curve):
#         if not trades:
#             raise ValueError("Sin trades.")

#         pnls   = np.array([t['pnl'] for t in trades])
#         wins   = [t for t in trades if t['won']]
#         losses = [t for t in trades if not t['won']]
#         eq     = np.array(equity_curve)

#         peak   = np.maximum.accumulate(eq)
#         dd     = (peak - eq) / peak
#         max_dd = float(np.max(dd))

#         daily_ret = np.diff(eq) / eq[:-1]
#         sharpe    = (float(np.mean(daily_ret)) /
#                     (float(np.std(daily_ret)) + 1e-10)) * np.sqrt(252)

#         neg_ret = daily_ret[daily_ret < 0]
#         sortino = (float(np.mean(daily_ret)) /
#                   (float(np.std(neg_ret)) + 1e-10)) * np.sqrt(252)

#         gp = sum(t['pnl'] for t in wins)
#         gl = abs(sum(t['pnl'] for t in losses))
#         pf = gp / (gl + 1e-10)

#         return BacktestResult(
#             total_trades   = len(trades),
#             winning_trades = len(wins),
#             losing_trades  = len(losses),
#             win_rate       = len(wins) / len(trades),
#             profit_factor  = round(pf, 3),
#             sharpe_ratio   = round(sharpe, 3),
#             sortino_ratio  = round(sortino, 3),
#             max_drawdown   = round(max_dd, 4),
#             total_return   = round((eq[-1] - eq[0]) / eq[0], 4),
#             avg_win        = round(gp / (len(wins) + 1e-10), 2),
#             avg_loss       = round(gl / (len(losses) + 1e-10), 2),
#             expectancy     = round(float(np.mean(pnls)), 2),
#             equity_curve   = list(eq)
#         )

import os
import pandas as pd
import numpy as np
from backtest.backtester import BacktestResult


class GBPBacktester:
    """
    Backtester GBPUSD M5:
    - SuperTrend flip + EMA trend filter + ADX regime + ATR filter
    - Entrada en la vela siguiente a la señal
    - Resolución conservadora de velas ambiguas
    - Timeout real al precio de cierre
    - Registro detallado de trades
    - Parámetros configurables para grids
    """

    ST_PERIOD = 10
    ST_MULT = 3.0

    ADX_PERIOD = 14

    EMA_FAST = 50
    EMA_SLOW = 200

    ATR_PERIOD = 14
    ATR_MIN = 0.0004

    MAX_TRADES_DAY = 1
    MAX_HOLD_BARS = 30

    SPREAD = 0.00010
    SLIPPAGE = 0.00002

    FILTER_XMAS = True
    USE_WORST_CASE_INTRABAR = True

    def __init__(
        self,
        initial_balance: float = 10000,
        risk_per_trade: float = 0.005,
        rr_ratio: float = 1.4,
        atr_sl_mult: float = 1.2,
        symbol: str = "GBPUSD",
        export_trades: bool = True,
        session_start: int = 7,
        session_end: int = 17,
        adx_min: float = 20,
        adx_max: float = 60,
        trade_mode: str = "BOTH",
    ):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.rr_ratio = rr_ratio
        self.atr_sl_mult = atr_sl_mult
        self.symbol = symbol
        self.export_trades = export_trades

        self.session_start = session_start
        self.session_end = session_end
        self.adx_min = adx_min
        self.adx_max = adx_max
        self.trade_mode = trade_mode.upper()

    def load_data(self) -> pd.DataFrame:
        df = pd.read_csv(
            f"backtest/data/{self.symbol}_5M.csv",
            index_col=0,
            parse_dates=True
        )
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()

    def _add_supertrend(self, df: pd.DataFrame) -> pd.DataFrame:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        n = len(df)

        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        atr = np.zeros(n)
        for i in range(self.ST_PERIOD, n):
            atr[i] = np.mean(tr[i - self.ST_PERIOD + 1:i + 1])

        hl2 = (high + low) / 2
        upper_basic = hl2 + self.ST_MULT * atr
        lower_basic = hl2 - self.ST_MULT * atr

        upper = upper_basic.copy()
        lower = lower_basic.copy()
        direction = np.ones(n)
        supertrend = np.zeros(n)

        for i in range(1, n):
            if upper_basic[i] < upper[i - 1] or close[i - 1] > upper[i - 1]:
                upper[i] = upper_basic[i]
            else:
                upper[i] = upper[i - 1]

            if lower_basic[i] > lower[i - 1] or close[i - 1] < lower[i - 1]:
                lower[i] = lower_basic[i]
            else:
                lower[i] = lower[i - 1]

            if direction[i - 1] == -1 and close[i] > upper[i]:
                direction[i] = 1
            elif direction[i - 1] == 1 and close[i] < lower[i]:
                direction[i] = -1
            else:
                direction[i] = direction[i - 1]

            supertrend[i] = lower[i] if direction[i] == 1 else upper[i]

        supertrend[:self.ST_PERIOD] = np.nan

        df["supertrend"] = supertrend
        df["st_direction"] = direction
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

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        hl = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"] - df["close"].shift()).abs()
        df["atr"] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(self.ATR_PERIOD).mean()
        return df

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
        path = f"backtest/results/{self.symbol.lower()}_gbp_strategy_trades.csv"
        trades_df.to_csv(path, index=False)
        print(f"Trades guardados en: {path}")

    def run(self) -> BacktestResult:
        df = self.load_data()
        df = self._add_supertrend(df)
        df = self._add_adx(df)
        df = self._add_atr(df)

        df["ema50"] = df["close"].ewm(span=self.EMA_FAST, adjust=False).mean()
        df["ema200"] = df["close"].ewm(span=self.EMA_SLOW, adjust=False).mean()

        df["hour"] = df.index.hour
        df["day"] = df.index.day
        df["month"] = df.index.month
        df["date"] = df.index.date
        df["weekday"] = df.index.weekday

        cols = ["supertrend", "st_direction", "adx", "atr", "ema50", "ema200"]
        df = df.dropna(subset=cols).copy()

        print(
            f"{self.symbol} 5M: {len(df)} velas | "
            f"Mode: {self.trade_mode} | "
            f"Session: {self.session_start}-{self.session_end} | "
            f"ADX: {self.adx_min}-{self.adx_max} | "
            f"RR: {self.rr_ratio} | SLxATR: {self.atr_sl_mult}"
        )

        balance = self.initial_balance
        equity_curve = [balance]
        trades = []
        trades_by_day = {}

        for i in range(220, len(df) - self.MAX_HOLD_BARS - 2):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            if row["hour"] < self.session_start or row["hour"] >= self.session_end:
                continue
            if row["weekday"] >= 5:
                continue
            if self.FILTER_XMAS and self._is_xmas_period(row):
                continue

            date = row["date"]
            if trades_by_day.get(date, 0) >= self.MAX_TRADES_DAY:
                continue

            curr_atr = float(row["atr"])
            adx = float(row["adx"])

            if curr_atr < self.ATR_MIN:
                continue
            if adx < self.adx_min or adx > self.adx_max:
                continue

            trend_bull = float(row["ema50"]) > float(row["ema200"])
            trend_bear = float(row["ema50"]) < float(row["ema200"])
            curr_dir = float(row["st_direction"])
            prev_dir = float(prev["st_direction"])

            signal_val = None
            signal_time = df.index[i]

            if prev_dir == -1 and curr_dir == 1 and trend_bull:
                signal_val = "BUY"
            elif prev_dir == 1 and curr_dir == -1 and trend_bear:
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
                sl = entry - curr_atr * self.atr_sl_mult
                tp = entry + curr_atr * self.atr_sl_mult * self.rr_ratio
                risk_per_unit = entry - sl
            else:
                entry = raw_entry - self.SPREAD / 2 - self.SLIPPAGE
                sl = entry + curr_atr * self.atr_sl_mult
                tp = entry - curr_atr * self.atr_sl_mult * self.rr_ratio
                risk_per_unit = sl - entry

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
                        exit_time = df.index[j]
                        exit_reason = "sl"
                        won = False
                        break

                    if hit_tp:
                        exit_price = tp
                        exit_time = df.index[j]
                        exit_reason = "tp"
                        won = True
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
                        exit_time = df.index[j]
                        exit_reason = "sl"
                        won = False
                        break

                    if hit_tp:
                        exit_price = tp
                        exit_time = df.index[j]
                        exit_reason = "tp"
                        won = True
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
                "entry": round(entry, 6),
                "exit": round(float(exit_price), 6),
                "sl": round(float(sl), 6),
                "tp": round(float(tp), 6),
                "atr": round(curr_atr, 6),
                "adx": round(adx, 4),
                "ema50": round(float(row["ema50"]), 6),
                "ema200": round(float(row["ema200"]), 6),
                "st_direction_prev": int(prev_dir),
                "st_direction_curr": int(curr_dir),
                "signal_hour": int(pd.to_datetime(signal_time).hour),
                "entry_hour": int(pd.to_datetime(entry_time).hour),
                "weekday": int(row["weekday"]),
                "month": int(row["month"]),
                "risk_amt": round(risk_amt, 2),
                "risk_per_unit": round(risk_per_unit, 6),
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