# backtest/backtester.py — Multi-Timeframe: 1H + 15M + 5M

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List

@dataclass
class BacktestResult:
    total_trades:   int
    winning_trades: int
    losing_trades:  int
    win_rate:       float
    profit_factor:  float
    sharpe_ratio:   float
    sortino_ratio:  float
    max_drawdown:   float
    total_return:   float
    avg_win:        float
    avg_loss:       float
    expectancy:     float
    equity_curve:   List[float] = field(default_factory=list)

    def passes_ftmo_filter(self) -> bool:
        return (
            self.sharpe_ratio   >= 1.5 and
            self.win_rate       >= 0.45 and
            self.max_drawdown   <= 0.08 and
            self.profit_factor  >= 1.3
        )

    def print_report(self):
        sep = "-" * 45
        print(f"\n{sep}")
        print("  BACKTEST REPORT - FTMO SCALPER MTF")
        print(sep)
        print(f"  Trades totales   : {self.total_trades}")
        print(f"  Win Rate         : {self.win_rate*100:.1f}%  (min 45%)")
        print(f"  Profit Factor    : {self.profit_factor:.2f}  (min 1.3)")
        print(f"  Sharpe Ratio     : {self.sharpe_ratio:.2f}  (min 1.5)")
        print(f"  Sortino Ratio    : {self.sortino_ratio:.2f}")
        print(f"  Max Drawdown     : {self.max_drawdown*100:.1f}%  (max 8%)")
        print(f"  Retorno Total    : {self.total_return*100:.1f}%")
        print(f"  Avg Win          : ${self.avg_win:.2f}")
        print(f"  Avg Loss         : ${self.avg_loss:.2f}")
        print(f"  Expectancy/Trade : ${self.expectancy:.2f}")
        print(sep)
        verdict = "APROBADO - Puede ir a paper trading" \
                  if self.passes_ftmo_filter() \
                  else "RECHAZADO - Optimizar estrategia"
        print(f"  Veredicto: {verdict}")
        print(f"{sep}\n")


class FTMOBacktester:

    EMA_TREND   = 200
    EMA_FAST    = 20
    EMA_SLOW    = 50
    ADX_PERIOD  = 14
    ADX_MIN     = 15
    RSI_PERIOD  = 14
    ATR_PERIOD  = 14
    ATR_SL_MULT = 1.2
    RR_RATIO    = 1.6
    ATR_MIN     = 0.0003

    def __init__(self, initial_balance: float = 10000,
                 risk_per_trade: float = 0.005,
                 rr_ratio: float = 1.6):
        self.initial_balance = initial_balance
        self.risk_per_trade  = risk_per_trade
        self.rr_ratio        = rr_ratio

    def load_data(self) -> tuple:
        def read(path):
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            df.columns = [c.lower() for c in df.columns]
            return df.sort_index()

        df_5m  = read("backtest/data/EURUSD_5M.csv")
        df_15m = read("backtest/data/EURUSD_15M.csv")
        df_1h  = read("backtest/data/EURUSD_1H.csv")
        print(f"5M: {len(df_5m)} | 15M: {len(df_15m)} | 1H: {len(df_1h)} velas")
        return df_5m, df_15m, df_1h

    def _add_ema(self, df: pd.DataFrame, span: int, col: str) -> pd.DataFrame:
        df[col] = df['close'].ewm(span=span, adjust=False).mean()
        return df

    def _add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        high  = df['high']
        low   = df['low']
        close = df['close']
        plus_dm  = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0]   = 0
        minus_dm[minus_dm < 0] = 0
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr      = tr.rolling(self.ADX_PERIOD).mean()
        plus_di  = 100 * plus_dm.rolling(self.ADX_PERIOD).mean()  / (atr + 1e-10)
        minus_di = 100 * minus_dm.rolling(self.ADX_PERIOD).mean() / (atr + 1e-10)
        dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        df['adx']      = dx.rolling(self.ADX_PERIOD).mean()
        df['plus_di']  = plus_di
        df['minus_di'] = minus_di
        return df

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        delta = df['close'].diff()
        gain  = delta.where(delta > 0, 0).rolling(self.RSI_PERIOD).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(self.RSI_PERIOD).mean()
        df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-10)))
        return df

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        hl  = df['high'] - df['low']
        hcp = (df['high'] - df['close'].shift()).abs()
        lcp = (df['low']  - df['close'].shift()).abs()
        df['atr'] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(self.ATR_PERIOD).mean()
        return df

    def _prepare_1h(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._add_ema(df, self.EMA_TREND, 'ema200')
        df = self._add_adx(df)
        df['bias_bull'] = (
            (df['close'] > df['ema200']) &
            (df['adx'] > self.ADX_MIN) &
            (df['plus_di'] > df['minus_di'])
        )
        df['bias_bear'] = (
            (df['close'] < df['ema200']) &
            (df['adx'] > self.ADX_MIN) &
            (df['minus_di'] > df['plus_di'])
        )
        return df.dropna()

    def _prepare_15m(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._add_ema(df, self.EMA_FAST, 'ema20')
        df = self._add_ema(df, self.EMA_SLOW, 'ema50')
        df = self._add_rsi(df)
        df['setup_bull'] = (
            (df['ema20'] > df['ema50']) &
            (df['rsi'] > 45) &
            (df['rsi'] < 75)
        )
        df['setup_bear'] = (
            (df['ema20'] < df['ema50']) &
            (df['rsi'] < 55) &
            (df['rsi'] > 25)
        )
        return df.dropna()

    def _prepare_5m(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._add_atr(df)
        df = self._add_ema(df, 9,  'ema9')
        df = self._add_ema(df, 21, 'ema21')
        df['hour']    = df.index.hour
        df['session'] = (df['hour'] >= 7) & (df['hour'] < 17)
        return df.dropna()

    def run(self) -> BacktestResult:
        df_5m, df_15m, df_1h = self.load_data()

        df_1h  = self._prepare_1h(df_1h)
        df_15m = self._prepare_15m(df_15m)
        df_5m  = self._prepare_5m(df_5m)

        balance      = self.initial_balance
        equity_curve = [balance]
        trades       = []

        for i in range(50, len(df_5m) - 10):
            row_5m = df_5m.iloc[i]
            ts     = df_5m.index[i]

            if not row_5m['session']: continue
            if ts.weekday() >= 5: continue

            curr_atr = float(row_5m['atr'])
            if curr_atr < self.ATR_MIN: continue

            # Contexto 1H
            idx_1h = df_1h.index.searchsorted(ts) - 1
            if idx_1h < 0 or idx_1h >= len(df_1h): continue
            row_1h = df_1h.iloc[idx_1h]

            # Setup 15M
            idx_15m = df_15m.index.searchsorted(ts) - 1
            if idx_15m < 0 or idx_15m >= len(df_15m): continue
            row_15m = df_15m.iloc[idx_15m]

            # Cruce EMA 9/21 en 5M
            prev_5m = df_5m.iloc[i - 1]
            ema9_cross_up   = (float(prev_5m['ema9']) <= float(prev_5m['ema21'])) and \
                              (float(row_5m['ema9'])  >  float(row_5m['ema21']))
            ema9_cross_down = (float(prev_5m['ema9']) >= float(prev_5m['ema21'])) and \
                              (float(row_5m['ema9'])  <  float(row_5m['ema21']))

            signal = None
            entry  = float(row_5m['close'])

            if row_1h['bias_bull'] and row_15m['setup_bull'] and ema9_cross_up:
                signal = 'BUY'
                sl = entry - curr_atr * self.ATR_SL_MULT
                tp = entry + curr_atr * self.ATR_SL_MULT * self.rr_ratio

            elif row_1h['bias_bear'] and row_15m['setup_bear'] and ema9_cross_down:
                signal = 'SELL'
                sl = entry + curr_atr * self.ATR_SL_MULT
                tp = entry - curr_atr * self.ATR_SL_MULT * self.rr_ratio

            if not signal: continue

            risk_amt = balance * self.risk_per_trade
            won = False

            for j in range(i + 1, min(i + 20, len(df_5m))):
                fh = float(df_5m.iloc[j]['high'])
                fl = float(df_5m.iloc[j]['low'])
                if signal == 'BUY':
                    if fh >= tp: won = True;  break
                    if fl <= sl: won = False; break
                else:
                    if fl <= tp: won = True;  break
                    if fh >= sl: won = False; break

            pnl = risk_amt * self.rr_ratio if won else -risk_amt
            balance += pnl
            equity_curve.append(balance)
            trades.append({'pnl': pnl, 'won': won})

        return self._compute_metrics(trades, equity_curve)

    def _compute_metrics(self, trades: list, equity_curve: list) -> BacktestResult:
        if not trades:
            raise ValueError("Sin trades. Revisar filtros.")

        pnls   = np.array([t['pnl'] for t in trades])
        wins   = [t for t in trades if t['won']]
        losses = [t for t in trades if not t['won']]
        eq     = np.array(equity_curve)

        peak   = np.maximum.accumulate(eq)
        dd     = (peak - eq) / peak
        max_dd = float(np.max(dd))

        daily_ret = np.diff(eq) / eq[:-1]
        sharpe    = (float(np.mean(daily_ret)) /
                    (float(np.std(daily_ret)) + 1e-10)) * np.sqrt(252)

        neg_ret = daily_ret[daily_ret < 0]
        sortino = (float(np.mean(daily_ret)) /
                  (float(np.std(neg_ret)) + 1e-10)) * np.sqrt(252)

        gp = sum(t['pnl'] for t in wins)
        gl = abs(sum(t['pnl'] for t in losses))
        pf = gp / (gl + 1e-10)

        return BacktestResult(
            total_trades   = len(trades),
            winning_trades = len(wins),
            losing_trades  = len(losses),
            win_rate       = len(wins) / len(trades),
            profit_factor  = round(pf, 3),
            sharpe_ratio   = round(sharpe, 3),
            sortino_ratio  = round(sortino, 3),
            max_drawdown   = round(max_dd, 4),
            total_return   = round((eq[-1] - eq[0]) / eq[0], 4),
            avg_win        = round(gp / (len(wins) + 1e-10), 2),
            avg_loss       = round(gl / (len(losses) + 1e-10), 2),
            expectancy     = round(float(np.mean(pnls)), 2),
            equity_curve   = list(eq)
        )