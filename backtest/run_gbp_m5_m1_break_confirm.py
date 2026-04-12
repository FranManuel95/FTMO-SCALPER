import os
import numpy as np
import pandas as pd


def compute_supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.DataFrame:
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
    for i in range(period, n):
        atr[i] = np.mean(tr[i - period + 1:i + 1])

    hl2 = (high + low) / 2
    upper_basic = hl2 + mult * atr
    lower_basic = hl2 - mult * atr

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

    supertrend[:period] = np.nan
    df["supertrend"] = supertrend
    df["st_direction"] = direction
    return df


def compute_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
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

    atr = tr.rolling(period).mean()
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    plus_di = 100 * plus_dm.rolling(period).mean() / (atr + 1e-10)
    minus_di = 100 * minus_dm.rolling(period).mean() / (atr + 1e-10)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(period).mean()

    df["adx"] = adx
    return df


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    hl = df["high"] - df["low"]
    hcp = (df["high"] - df["close"].shift()).abs()
    lcp = (df["low"] - df["close"].shift()).abs()
    df["atr"] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(period).mean()
    return df


def load_m5() -> pd.DataFrame:
    df = pd.read_csv("backtest/data/GBPUSD_5M.csv", index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_index()

    df = compute_supertrend(df, 10, 3.0)
    df = compute_adx(df, 14)
    df = compute_atr(df, 14)

    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["hour"] = df.index.hour
    df["day"] = df.index.day
    df["month"] = df.index.month
    df["date"] = df.index.date
    df["weekday"] = df.index.weekday

    df = df.dropna(subset=["supertrend", "st_direction", "adx", "atr", "ema50", "ema200"]).copy()
    return df


def load_m1() -> pd.DataFrame:
    df = pd.read_csv("backtest/data/GBPUSD_1M.csv", index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df.sort_index()
    df["hour"] = df.index.hour
    return df


def is_xmas(row: pd.Series) -> bool:
    return ((row["month"] == 12 and row["day"] >= 20) or
            (row["month"] == 1 and row["day"] <= 3))


def summarize_results(trades_df: pd.DataFrame, initial_balance: float):
    pnls = trades_df["pnl"].values
    wins_df = trades_df[trades_df["pnl"] > 0]
    losses_df = trades_df[trades_df["pnl"] <= 0]

    balance = initial_balance
    eq = [balance]
    for pnl in pnls:
        balance += pnl
        eq.append(balance)

    eq = np.array(eq, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    max_dd = float(np.max(dd))

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
            no_entry=("exit_reason", lambda s: int((s == "no_entry").sum())),
        )
        .reset_index()
    )
    monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(2)

    print("\n=== RESUMEN MENSUAL ===")
    print(monthly.to_string(index=False))

    print("\n=== RESULTADO M5 + M1 BREAK CONFIRM ===")
    print(f"Total trades:   {len(trades_df)}")
    print(f"Winning trades: {int((trades_df['pnl'] > 0).sum())}")
    print(f"Losing trades:  {int((trades_df['pnl'] <= 0).sum())}")
    print(f"Win rate:       {(trades_df['pnl'] > 0).mean() * 100:.2f}%")
    print(f"Profit factor:  {round(pf, 3)}")
    print(f"Max drawdown:   {max_dd * 100:.2f}%")
    print(f"Total return:   {((eq[-1] - eq[0]) / eq[0]) * 100:.2f}%")
    print(f"Avg win:        {round(float(wins_df['pnl'].mean()) if not wins_df.empty else 0.0, 2)}")
    print(f"Avg loss:       {round(abs(float(losses_df['pnl'].mean())) if not losses_df.empty else 0.0, 2)}")
    print(f"Expectancy:     {round(float(np.mean(pnls)), 2)}")


def main():
    INITIAL_BALANCE = 10000
    RISK_PER_TRADE = 0.005

    # Setup ganador M5
    SESSION_START = 8
    SESSION_END = 13
    ADX_MIN = 30
    ADX_MAX = 38
    ATR_MIN = 0.0004
    RR_RATIO = 1.4
    ATR_SL_MULT = 1.0
    SPREAD = 0.00010
    SLIPPAGE = 0.00002
    MAX_HOLD_M5_BARS = 30
    MAX_TRADES_DAY = 1

    # Capa M1
    M1_CONFIRM_WINDOW = 10
    M1_BREAK_LOOKBACK = 3

    m5 = load_m5()
    m1 = load_m1()

    print(f"GBPUSD M5: {len(m5)} velas")
    print(f"GBPUSD M1: {len(m1)} velas")
    print(
        f"Mode: SELL_ONLY | Session: {SESSION_START}-{SESSION_END} | "
        f"ADX: {ADX_MIN}-{ADX_MAX} | RR: {RR_RATIO} | SLxATR: {ATR_SL_MULT} | "
        f"M1 break lookback: {M1_BREAK_LOOKBACK} | confirm window: {M1_CONFIRM_WINDOW}"
    )

    balance = INITIAL_BALANCE
    trades = []
    trades_by_day = {}

    for i in range(220, len(m5) - MAX_HOLD_M5_BARS - 2):
        row = m5.iloc[i]
        prev = m5.iloc[i - 1]

        if row["hour"] < SESSION_START or row["hour"] >= SESSION_END:
            continue
        if row["weekday"] >= 5:
            continue
        if is_xmas(row):
            continue

        date = row["date"]
        if trades_by_day.get(date, 0) >= MAX_TRADES_DAY:
            continue

        curr_atr = float(row["atr"])
        adx = float(row["adx"])

        if curr_atr < ATR_MIN:
            continue
        if adx < ADX_MIN or adx > ADX_MAX:
            continue

        trend_bear = float(row["ema50"]) < float(row["ema200"])
        curr_dir = float(row["st_direction"])
        prev_dir = float(prev["st_direction"])

        # SOLO SELL
        signal_val = None
        if prev_dir == 1 and curr_dir == -1 and trend_bear:
            signal_val = "SELL"

        if signal_val != "SELL":
            continue

        signal_time = m5.index[i]
        confirm_start = signal_time + pd.Timedelta(minutes=1)
        confirm_end = signal_time + pd.Timedelta(minutes=M1_CONFIRM_WINDOW)

        m1_window = m1.loc[(m1.index >= confirm_start) & (m1.index <= confirm_end)].copy()
        if len(m1_window) < M1_BREAK_LOOKBACK + 1:
            continue

        entry_time = None
        entry_price = None

        m1_window = m1_window.copy()
        for k in range(M1_BREAK_LOOKBACK, len(m1_window)):
            hist_slice = m1_window.iloc[k - M1_BREAK_LOOKBACK:k]
            trigger_low = float(hist_slice["low"].min())
            curr_m1 = m1_window.iloc[k]

            # Confirmación: rompe el mínimo reciente
            if float(curr_m1["low"]) < trigger_low:
                raw_entry = min(float(curr_m1["open"]), trigger_low)
                entry_price = raw_entry - SPREAD / 2 - SLIPPAGE
                entry_time = m1_window.index[k]
                break

        if entry_time is None:
            continue

        sl = entry_price + curr_atr * ATR_SL_MULT
        tp = entry_price - curr_atr * ATR_SL_MULT * RR_RATIO
        risk_per_unit = sl - entry_price

        if risk_per_unit <= 0:
            continue

        trades_by_day[date] = trades_by_day.get(date, 0) + 1
        risk_amt = balance * RISK_PER_TRADE

        exit_price = None
        exit_time = None
        exit_reason = None
        bars_held = 0

        # Salidas se siguen resolviendo sobre M5 para mantener coherencia
        last_j = min(i + 1 + MAX_HOLD_M5_BARS, len(m5) - 1)

        # buscamos desde la vela M5 posterior a la señal
        for j in range(i + 1, last_j + 1):
            fut = m5.iloc[j]
            fh = float(fut["high"])
            fl = float(fut["low"])
            bars_held += 1

            hit_tp = fl <= tp
            hit_sl = fh >= sl

            if hit_tp and hit_sl:
                exit_price = sl
                exit_reason = "ambiguous_sl"
                exit_time = m5.index[j]
                break

            if hit_sl:
                exit_price = sl
                exit_reason = "sl"
                exit_time = m5.index[j]
                break

            if hit_tp:
                exit_price = tp
                exit_reason = "tp"
                exit_time = m5.index[j]
                break

        if exit_price is None:
            timeout_row = m5.iloc[last_j]
            raw_exit = float(timeout_row["close"])
            exit_price = raw_exit + SPREAD / 2 + SLIPPAGE
            pnl_r = (entry_price - exit_price) / risk_per_unit
            exit_time = m5.index[last_j]
            exit_reason = "timeout"
        else:
            pnl_r = (entry_price - exit_price) / risk_per_unit

        pnl = risk_amt * pnl_r
        won = pnl > 0
        balance += pnl

        trades.append({
            "signal_time": signal_time,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_date": pd.to_datetime(entry_time).date(),
            "exit_date": pd.to_datetime(exit_time).date(),
            "side": "SELL",
            "entry": round(entry_price, 6),
            "exit": round(float(exit_price), 6),
            "sl": round(float(sl), 6),
            "tp": round(float(tp), 6),
            "atr": round(curr_atr, 6),
            "adx": round(adx, 4),
            "entry_hour": int(pd.to_datetime(entry_time).hour),
            "weekday": int(row["weekday"]),
            "month": int(row["month"]),
            "risk_amt": round(risk_amt, 2),
            "pnl": round(float(pnl), 2),
            "pnl_r": round(float(pnl_r), 4),
            "won": bool(won),
            "exit_reason": exit_reason,
            "bars_held": int(bars_held),
            "balance_after": round(balance, 2),
        })

    if not trades:
        raise ValueError("Sin trades en M5+M1.")

    trades_df = pd.DataFrame(trades)

    os.makedirs("backtest/results", exist_ok=True)
    out_path = "backtest/results/gbpusd_m5_m1_break_confirm_trades.csv"
    trades_df.to_csv(out_path, index=False)
    print(f"\nTrades guardados en: {out_path}")

    summarize_results(trades_df, INITIAL_BALANCE)
    print("\n=== MUESTRA TRADES ===")
    print(trades_df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()