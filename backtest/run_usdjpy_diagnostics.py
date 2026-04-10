from backtest.backtester_usdjpy import USDJPYBacktester


def main():
    bt = USDJPYBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.3,
        symbol="USDJPY"
    )

    df = bt.prepare_dataframe()
    print(f"{bt.symbol} 5M: {len(df)} velas")
    print(f"Rango fechas: {df.index.min()} -> {df.index.max()}")
    print("\nPrimeras velas:")
    print(df[["open", "high", "low", "close"]].head(5).to_string())

    counts = {
        "total_rows": 0,
        "session": 0,
        "weekday": 0,
        "friday_cutoff": 0,
        "not_xmas": 0,
        "atr_ok": 0,
        "adx_ok": 0,
        "asia_range_ok": 0,
        "body_ok": 0,
        "breakout_up": 0,
        "breakout_dn": 0,
        "ema_bull": 0,
        "ema_bear": 0,
        "above_vwap": 0,
        "below_vwap": 0,
        "buy_signal": 0,
        "sell_signal": 0,
        "final_signals": 0,
    }

    for i in range(120, len(df) - 5):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        counts["total_rows"] += 1

        in_session = bt.SESSION_START <= row["hour"] < bt.SESSION_END
        if not in_session:
            continue
        counts["session"] += 1

        if row["weekday"] >= 5:
            continue
        counts["weekday"] += 1

        if row["weekday"] == 4 and row["hour"] >= bt.FRIDAY_CUTOFF_HOUR:
            continue
        counts["friday_cutoff"] += 1

        is_xmas = (
            (row["month"] == 12 and row["day"] >= 20) or
            (row["month"] == 1 and row["day"] <= 3)
        )
        if is_xmas:
            continue
        counts["not_xmas"] += 1

        curr_atr = float(row["atr"])
        if curr_atr < bt.ATR_MIN:
            continue
        counts["atr_ok"] += 1

        adx = float(row["adx"])
        if adx < bt.ADX_MIN or adx > bt.ADX_MAX:
            continue
        counts["adx_ok"] += 1

        asia_range = float(row["asia_range"])
        if asia_range <= 0 or asia_range > curr_atr * bt.RANGE_ATR_CAP:
            continue
        counts["asia_range_ok"] += 1

        body_ratio = bt._body_ratio(row)
        if body_ratio < bt.MIN_BODY_RATIO:
            continue
        counts["body_ok"] += 1

        ema_bull = float(row["ema_fast"]) > float(row["ema_slow"])
        ema_bear = float(row["ema_fast"]) < float(row["ema_slow"])
        above_vwap = float(row["close"]) > float(row["vwap"])
        below_vwap = float(row["close"]) < float(row["vwap"])

        if ema_bull:
            counts["ema_bull"] += 1
        if ema_bear:
            counts["ema_bear"] += 1
        if above_vwap:
            counts["above_vwap"] += 1
        if below_vwap:
            counts["below_vwap"] += 1

        asia_high = float(row["asia_high"])
        asia_low = float(row["asia_low"])
        prev_close = float(prev["close"])
        curr_close = float(row["close"])

        breakout_up = prev_close <= asia_high and curr_close > (asia_high + bt.BUFFER_PIPS)
        breakout_dn = prev_close >= asia_low and curr_close < (asia_low - bt.BUFFER_PIPS)

        if breakout_up:
            counts["breakout_up"] += 1
        if breakout_dn:
            counts["breakout_dn"] += 1

        buy_signal = breakout_up and ema_bull and above_vwap
        sell_signal = breakout_dn and ema_bear and below_vwap

        if buy_signal:
            counts["buy_signal"] += 1
        if sell_signal:
            counts["sell_signal"] += 1
        if buy_signal or sell_signal:
            counts["final_signals"] += 1

    print("\n=== DIAGNOSTICO POR FILTROS ===")
    for k, v in counts.items():
        print(f"{k}: {v}")

    print("\n=== PARAMETROS ACTUALES ===")
    print(f"ASIA_START={bt.ASIA_START}")
    print(f"ASIA_END={bt.ASIA_END}")
    print(f"SESSION_START={bt.SESSION_START}")
    print(f"SESSION_END={bt.SESSION_END}")
    print(f"BUFFER_PIPS={bt.BUFFER_PIPS}")
    print(f"ATR_MIN={bt.ATR_MIN}")
    print(f"ADX_MIN={bt.ADX_MIN}")
    print(f"ADX_MAX={bt.ADX_MAX}")
    print(f"MIN_BODY_RATIO={bt.MIN_BODY_RATIO}")
    print(f"RANGE_ATR_CAP={bt.RANGE_ATR_CAP}")


if __name__ == "__main__":
    main()