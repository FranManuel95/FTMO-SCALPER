# backtest/walk_forward.py — Walk-Forward EURUSD + GBPUSD + XAUUSD

import pandas as pd
import numpy as np
from backtest.backtester     import FTMOBacktester
from backtest.backtester_gbp import GBPBacktester
from backtest.backtester_xau import XAUBacktester


def run_walk_forward(n_windows: int = 4):

    def read(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()

    df_5m  = read("backtest/data/EURUSD_5M.csv")
    df_15m = read("backtest/data/EURUSD_15M.csv")
    df_1h  = read("backtest/data/EURUSD_1H.csv")

    total    = len(df_5m)
    win_size = total // n_windows

    print(f"\n{'='*52}")
    print(f"  WALK-FORWARD EURUSD MTF v2 — {n_windows} ventanas")
    print(f"  Total velas 5M: {total}")
    print(f"{'='*52}\n")

    results = []

    for w in range(n_windows):
        start = w * win_size
        end   = start + win_size if w < n_windows - 1 else total
        split = start + int((end - start) * 0.70)

        date_start = df_5m.index[start]
        date_split = df_5m.index[split]
        date_end   = df_5m.index[end - 1]

        train_5m  = df_5m.iloc[start:split]
        test_5m   = df_5m.iloc[split:end]
        train_15m = df_15m[(df_15m.index >= date_start) & (df_15m.index < date_split)]
        test_15m  = df_15m[(df_15m.index >= date_split) & (df_15m.index <= date_end)]
        train_1h  = df_1h[(df_1h.index >= date_start)  & (df_1h.index < date_split)]
        test_1h   = df_1h[(df_1h.index >= date_split)  & (df_1h.index <= date_end)]

        print(f"Ventana {w+1}/{n_windows}")
        print(f"  Train: {date_start.strftime('%Y-%m-%d')} -> {date_split.strftime('%Y-%m-%d')} ({len(train_5m)} velas)")
        print(f"  Test:  {date_split.strftime('%Y-%m-%d')} -> {date_end.strftime('%Y-%m-%d')} ({len(test_5m)} velas)")

        train_r = _run_slice_eurusd(train_5m, train_15m, train_1h)
        test_r  = _run_slice_eurusd(test_5m,  test_15m,  test_1h)

        passed = (test_r['win_rate']      >= 0.40 and
                  test_r['profit_factor'] >= 1.0  and
                  test_r['max_dd']        <= 0.08)

        tag    = "OK" if passed else "XX"
        status = "ROBUSTO" if passed else "FRAGIL"

        print(f"  Train -> WR:{train_r['win_rate']*100:.0f}% PF:{train_r['profit_factor']:.2f} DD:{train_r['max_dd']*100:.1f}% Trades:{train_r['trades']}")
        print(f"  Test  -> WR:{test_r['win_rate']*100:.0f}%  PF:{test_r['profit_factor']:.2f} DD:{test_r['max_dd']*100:.1f}% Trades:{test_r['trades']} [{tag}] {status}")
        print()

        results.append({'window': w+1, 'passed': passed, 'test': test_r})

    _print_verdict(results, n_windows, "EURUSD")


def run_walk_forward_gbp(n_windows: int = 4):

    def read(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        return df.sort_index()

    df_5m    = read("backtest/data/GBPUSD_5M.csv")
    total    = len(df_5m)
    win_size = total // n_windows

    print(f"\n{'='*52}")
    print(f"  WALK-FORWARD GBPUSD SuperTrend — {n_windows} ventanas")
    print(f"  Total velas 5M: {total}")
    print(f"{'='*52}\n")

    results = []

    for w in range(n_windows):
        start = w * win_size
        end   = start + win_size if w < n_windows - 1 else total
        split = start + int((end - start) * 0.70)

        date_start = df_5m.index[start]
        date_split = df_5m.index[split]
        date_end   = df_5m.index[end - 1]

        train_5m = df_5m.iloc[start:split]
        test_5m  = df_5m.iloc[split:end]

        print(f"Ventana {w+1}/{n_windows}")
        print(f"  Train: {date_start.strftime('%Y-%m-%d')} -> {date_split.strftime('%Y-%m-%d')} ({len(train_5m)} velas)")
        print(f"  Test:  {date_split.strftime('%Y-%m-%d')} -> {date_end.strftime('%Y-%m-%d')} ({len(test_5m)} velas)")

        train_r = _run_slice_gbp(train_5m)
        test_r  = _run_slice_gbp(test_5m)

        passed = (test_r['win_rate']      >= 0.40 and
                  test_r['profit_factor'] >= 1.0  and
                  test_r['max_dd']        <= 0.08)

        tag    = "OK" if passed else "XX"
        status = "ROBUSTO" if passed else "FRAGIL"

        print(f"  Train -> WR:{train_r['win_rate']*100:.0f}% PF:{train_r['profit_factor']:.2f} DD:{train_r['max_dd']*100:.1f}% Trades:{train_r['trades']}")
        print(f"  Test  -> WR:{test_r['win_rate']*100:.0f}%  PF:{test_r['profit_factor']:.2f} DD:{test_r['max_dd']*100:.1f}% Trades:{test_r['trades']} [{tag}] {status}")
        print()

        results.append({'window': w+1, 'passed': passed, 'test': test_r})

    _print_verdict(results, n_windows, "GBPUSD")


def run_walk_forward_xau(n_windows: int = 4):

    def read(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col] * 100
        return df.sort_index()

    df_1h    = read("backtest/data/XAUUSD_1H.csv")
    total    = len(df_1h)
    win_size = total // n_windows

    print(f"\n{'='*52}")
    print(f"  WALK-FORWARD XAUUSD SuperTrend H1 — {n_windows} ventanas")
    print(f"  Total velas 1H: {total}")
    print(f"{'='*52}\n")

    results = []

    for w in range(n_windows):
        start = w * win_size
        end   = start + win_size if w < n_windows - 1 else total
        split = start + int((end - start) * 0.70)

        date_start = df_1h.index[start]
        date_split = df_1h.index[split]
        date_end   = df_1h.index[end - 1]

        train_1h = df_1h.iloc[start:split]
        test_1h  = df_1h.iloc[split:end]

        print(f"Ventana {w+1}/{n_windows}")
        print(f"  Train: {date_start.strftime('%Y-%m-%d')} -> {date_split.strftime('%Y-%m-%d')} ({len(train_1h)} velas)")
        print(f"  Test:  {date_split.strftime('%Y-%m-%d')} -> {date_end.strftime('%Y-%m-%d')} ({len(test_1h)} velas)")

        train_r = _run_slice_xau(train_1h)
        test_r  = _run_slice_xau(test_1h)

        passed = (test_r['win_rate']      >= 0.40 and
                  test_r['profit_factor'] >= 1.0  and
                  test_r['max_dd']        <= 0.08)

        tag    = "OK" if passed else "XX"
        status = "ROBUSTO" if passed else "FRAGIL"

        print(f"  Train -> WR:{train_r['win_rate']*100:.0f}% PF:{train_r['profit_factor']:.2f} DD:{train_r['max_dd']*100:.1f}% Trades:{train_r['trades']}")
        print(f"  Test  -> WR:{test_r['win_rate']*100:.0f}%  PF:{test_r['profit_factor']:.2f} DD:{test_r['max_dd']*100:.1f}% Trades:{test_r['trades']} [{tag}] {status}")
        print()

        results.append({'window': w+1, 'passed': passed, 'test': test_r})

    _print_verdict(results, n_windows, "XAUUSD")


def _print_verdict(results, n_windows, symbol):
    robust_count = sum(1 for r in results if r['passed'])
    robust_pct   = robust_count / n_windows * 100
    avg_wr       = np.mean([r['test']['win_rate'] for r in results]) * 100
    avg_pf       = np.mean([r['test']['profit_factor'] for r in results])
    avg_dd       = np.mean([r['test']['max_dd'] for r in results]) * 100

    print(f"{'='*52}")
    print(f"  VEREDICTO FINAL — {symbol}")
    print(f"{'='*52}")
    print(f"  Ventanas robustas : {robust_count}/{n_windows} ({robust_pct:.0f}%)")
    print(f"  WR promedio test  : {avg_wr:.1f}%")
    print(f"  PF promedio test  : {avg_pf:.2f}")
    print(f"  DD promedio test  : {avg_dd:.1f}%")
    print()

    if robust_pct >= 75:
        print(f"  ✅ ESTRATEGIA ROBUSTA - Proceder a paper trading")
    elif robust_pct >= 50:
        print(f"  ⚠️  ESTRATEGIA ACEPTABLE - Paper trading con cautela")
    else:
        print(f"  ❌ ESTRATEGIA FRAGIL - No usar en challenge")
    print(f"{'='*52}\n")


def _run_slice_eurusd(df_5m, df_15m, df_1h):
    bt    = FTMOBacktester(10000)
    df_1h  = bt._prepare_1h(df_1h.copy())
    df_15m = bt._prepare_15m(df_15m.copy())
    df_5m  = bt._prepare_5m(df_5m.copy())

    balance      = bt.initial_balance
    equity_curve = [balance]
    trades       = []

    for i in range(50, len(df_5m) - 20):
        row_5m = df_5m.iloc[i]
        ts     = df_5m.index[i]

        if not row_5m['session']: continue
        if ts.weekday() >= 5: continue

        curr_atr = float(row_5m['atr'])
        if curr_atr < bt.ATR_MIN: continue

        idx_1h = df_1h.index.searchsorted(ts) - 1
        if idx_1h < 0 or idx_1h >= len(df_1h): continue
        row_1h = df_1h.iloc[idx_1h]

        idx_15m = df_15m.index.searchsorted(ts) - 1
        if idx_15m < 0 or idx_15m >= len(df_15m): continue
        row_15m = df_15m.iloc[idx_15m]

        prev_5m   = df_5m.iloc[i-1]
        ema9_up   = (float(prev_5m['ema9']) <= float(prev_5m['ema21'])) and \
                    (float(row_5m['ema9'])  >  float(row_5m['ema21']))
        ema9_down = (float(prev_5m['ema9']) >= float(prev_5m['ema21'])) and \
                    (float(row_5m['ema9'])  <  float(row_5m['ema21']))

        signal = None
        entry  = float(row_5m['close'])

        if row_1h['bias_bull'] and row_15m['setup_bull'] and ema9_up:
            signal = 'BUY'
            sl = entry - curr_atr * bt.ATR_SL_MULT
            tp = entry + curr_atr * bt.ATR_SL_MULT * bt.rr_ratio
        elif row_1h['bias_bear'] and row_15m['setup_bear'] and ema9_down:
            signal = 'SELL'
            sl = entry + curr_atr * bt.ATR_SL_MULT
            tp = entry - curr_atr * bt.ATR_SL_MULT * bt.rr_ratio

        if not signal: continue

        risk_amt = balance * bt.risk_per_trade
        won      = False
        trail_sl = sl

        for j in range(i+1, min(i+30, len(df_5m))):
            fh      = float(df_5m.iloc[j]['high'])
            fl      = float(df_5m.iloc[j]['low'])
            fut_atr = float(df_5m.iloc[j]['atr'])

            if signal == 'BUY':
                new_trail = fh - fut_atr * bt.TRAIL_MULT
                trail_sl  = max(trail_sl, new_trail)
                if fh >= tp:       won = True;  break
                if fl <= trail_sl: won = False; break
            else:
                new_trail = fl + fut_atr * bt.TRAIL_MULT
                trail_sl  = min(trail_sl, new_trail)
                if fl <= tp:       won = True;  break
                if fh >= trail_sl: won = False; break

        pnl = risk_amt * bt.rr_ratio if won else -risk_amt
        balance += pnl
        equity_curve.append(balance)
        trades.append({'pnl': pnl, 'won': won})

    if not trades:
        return {'win_rate': 0, 'profit_factor': 0, 'max_dd': 1, 'trades': 0}

    eq     = np.array(equity_curve)
    peak   = np.maximum.accumulate(eq)
    max_dd = float(np.max((peak - eq) / peak))
    wins   = [t for t in trades if t['won']]
    losses = [t for t in trades if not t['won']]
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))

    return {
        'win_rate':      len(wins) / len(trades),
        'profit_factor': round(gp / (gl + 1e-10), 2),
        'max_dd':        round(max_dd, 4),
        'trades':        len(trades)
    }


def _run_slice_gbp(df_5m):
    bt = GBPBacktester(10000)
    df = df_5m.copy()
    df = bt._add_supertrend(df)
    df = bt._add_adx(df)
    df = bt._add_atr(df)

    df['ema50']   = df['close'].ewm(span=bt.EMA_FAST, adjust=False).mean()
    df['ema200']  = df['close'].ewm(span=bt.EMA_SLOW, adjust=False).mean()
    df['hour']    = df.index.hour
    df['date']    = df.index.date
    df['weekday'] = df.index.weekday

    cols = ['supertrend', 'st_direction', 'adx', 'atr', 'ema50', 'ema200']
    df = df.dropna(subset=cols)

    balance       = bt.initial_balance
    equity_curve  = [balance]
    trades        = []
    trades_by_day = {}

    for i in range(220, len(df) - 10):
        row  = df.iloc[i]
        prev = df.iloc[i-1]

        if row['hour'] < bt.SESSION_START or row['hour'] >= bt.SESSION_END: continue
        if row['weekday'] >= 5: continue

        date = row['date']
        if trades_by_day.get(date, 0) >= bt.MAX_TRADES_DAY: continue

        curr_atr = float(row['atr'])
        if curr_atr < bt.ATR_MIN: continue

        adx = float(row['adx'])
        if adx < bt.ADX_MIN or adx > bt.ADX_MAX: continue

        trend_bull = float(row['ema50']) > float(row['ema200'])
        trend_bear = float(row['ema50']) < float(row['ema200'])
        curr_dir   = float(row['st_direction'])
        prev_dir   = float(prev['st_direction'])

        signal_val = None
        entry = float(row['close'])

        if prev_dir == -1 and curr_dir == 1 and trend_bull:
            signal_val = 'BUY'
            sl = entry - curr_atr * bt.ATR_SL_MULT
            tp = entry + curr_atr * bt.ATR_SL_MULT * bt.rr_ratio
        elif prev_dir == 1 and curr_dir == -1 and trend_bear:
            signal_val = 'SELL'
            sl = entry + curr_atr * bt.ATR_SL_MULT
            tp = entry - curr_atr * bt.ATR_SL_MULT * bt.rr_ratio

        if not signal_val: continue

        trades_by_day[date] = trades_by_day.get(date, 0) + 1
        risk_amt = balance * bt.risk_per_trade
        won = False

        for j in range(i+1, min(i+30, len(df))):
            fh = float(df.iloc[j]['high'])
            fl = float(df.iloc[j]['low'])
            if signal_val == 'BUY':
                if fh >= tp: won = True;  break
                if fl <= sl: won = False; break
            else:
                if fl <= tp: won = True;  break
                if fh >= sl: won = False; break

        pnl = risk_amt * bt.rr_ratio if won else -risk_amt
        balance += pnl
        equity_curve.append(balance)
        trades.append({'pnl': pnl, 'won': won})

    if not trades:
        return {'win_rate': 0, 'profit_factor': 0, 'max_dd': 1, 'trades': 0}

    eq     = np.array(equity_curve)
    peak   = np.maximum.accumulate(eq)
    max_dd = float(np.max((peak - eq) / peak))
    wins   = [t for t in trades if t['won']]
    losses = [t for t in trades if not t['won']]
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))

    return {
        'win_rate':      len(wins) / len(trades),
        'profit_factor': round(gp / (gl + 1e-10), 2),
        'max_dd':        round(max_dd, 4),
        'trades':        len(trades)
    }


def _run_slice_xau(df_1h):
    bt = XAUBacktester(10000)
    df = df_1h.copy()
    df = bt._add_supertrend(df)
    df = bt._add_adx(df)
    df = bt._add_atr(df)

    df['ema20']   = df['close'].ewm(span=bt.EMA_FAST, adjust=False).mean()
    df['ema50']   = df['close'].ewm(span=bt.EMA_SLOW, adjust=False).mean()
    df['day']     = df.index.day
    df['month']   = df.index.month
    df['date']    = df.index.date
    df['weekday'] = df.index.weekday

    cols = ['supertrend', 'st_direction', 'adx', 'atr', 'ema20', 'ema50']
    df = df.dropna(subset=cols)

    balance       = bt.initial_balance
    equity_curve  = [balance]
    trades        = []
    trades_by_day = {}

    for i in range(60, len(df) - 5):
        row  = df.iloc[i]
        prev = df.iloc[i-1]

        if row['weekday'] >= 5: continue
        if (row['month'] == 12 and row['day'] >= 20) or \
           (row['month'] == 1  and row['day'] <= 3): continue

        date = row['date']
        if trades_by_day.get(date, 0) >= bt.MAX_TRADES_DAY: continue

        curr_atr = float(row['atr'])
        if curr_atr < bt.ATR_MIN: continue

        adx = float(row['adx'])
        if adx < bt.ADX_MIN or adx > bt.ADX_MAX: continue

        trend_bull = float(row['ema20']) > float(row['ema50'])
        trend_bear = float(row['ema20']) < float(row['ema50'])
        curr_dir   = float(row['st_direction'])
        prev_dir   = float(prev['st_direction'])

        signal_val = None
        entry = float(row['close'])

        if prev_dir == -1 and curr_dir == 1 and trend_bull:
            signal_val = 'BUY'
            sl = entry - curr_atr * bt.ATR_SL_MULT
            tp = entry + curr_atr * bt.ATR_SL_MULT * bt.rr_ratio
        elif prev_dir == 1 and curr_dir == -1 and trend_bear:
            signal_val = 'SELL'
            sl = entry + curr_atr * bt.ATR_SL_MULT
            tp = entry - curr_atr * bt.ATR_SL_MULT * bt.rr_ratio

        if not signal_val: continue

        trades_by_day[date] = trades_by_day.get(date, 0) + 1
        risk_amt = balance * bt.risk_per_trade
        won = False

        for j in range(i+1, min(i+30, len(df))):
            fh = float(df.iloc[j]['high'])
            fl = float(df.iloc[j]['low'])
            if signal_val == 'BUY':
                if fh >= tp: won = True;  break
                if fl <= sl: won = False; break
            else:
                if fl <= tp: won = True;  break
                if fh >= sl: won = False; break

        pnl = risk_amt * bt.rr_ratio if won else -risk_amt
        balance += pnl
        equity_curve.append(balance)
        trades.append({'pnl': pnl, 'won': won})

    if not trades:
        return {'win_rate': 0, 'profit_factor': 0, 'max_dd': 1, 'trades': 0}

    eq     = np.array(equity_curve)
    peak   = np.maximum.accumulate(eq)
    max_dd = float(np.max((peak - eq) / peak))
    wins   = [t for t in trades if t['won']]
    losses = [t for t in trades if not t['won']]
    gp     = sum(t['pnl'] for t in wins)
    gl     = abs(sum(t['pnl'] for t in losses))

    return {
        'win_rate':      len(wins) / len(trades),
        'profit_factor': round(gp / (gl + 1e-10), 2),
        'max_dd':        round(max_dd, 4),
        'trades':        len(trades)
    }


if __name__ == "__main__":
    run_walk_forward(n_windows=4)
    run_walk_forward_gbp(n_windows=4)
    run_walk_forward_xau(n_windows=4)