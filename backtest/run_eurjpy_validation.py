from backtest.backtester_eurjpy import EURJPYBacktester


def main():
    bt = EURJPYBacktester(
        symbol="EURJPY",
        export_trades=True,
        risk_per_trade=0.005,
        rr_ratio=1.4,
        atr_sl_mult=1.2,
        session_start=7,
        session_end=13,
        adx_min=18,
        adx_max=50,
        atr_min=0.08,
        breakout_buffer_atr=0.05,
        min_body_ratio=0.35,
        range_atr_min=0.4,
        range_atr_cap=4.0,
        trade_mode="BOTH",
        friday_cutoff_hour=12,
    )

    result = bt.run()
    result.print_report()


if __name__ == "__main__":
    main()