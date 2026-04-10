from backtest.backtester_gbp import GBPBacktester


def run_candidate(name: str, rr_ratio: float, atr_sl_mult: float):
    print(f"\n{'=' * 70}")
    print(f"CANDIDATA: {name}")
    print(f"{'=' * 70}")

    bt = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=rr_ratio,
        atr_sl_mult=atr_sl_mult,
        symbol="GBPUSD",
        export_trades=True,
        session_start=8,
        session_end=14,
        adx_min=30,
        adx_max=38,
        trade_mode="SELL_ONLY",
    )

    result = bt.run()

    print(f"\n=== RESULTADO {name} ===")
    print(f"Total trades:   {result.total_trades}")
    print(f"Winning trades: {result.winning_trades}")
    print(f"Losing trades:  {result.losing_trades}")
    print(f"Win rate:       {result.win_rate * 100:.2f}%")
    print(f"Profit factor:  {result.profit_factor}")
    print(f"Sharpe:         {result.sharpe_ratio}")
    print(f"Sortino:        {result.sortino_ratio}")
    print(f"Max drawdown:   {result.max_drawdown * 100:.2f}%")
    print(f"Total return:   {result.total_return * 100:.2f}%")
    print(f"Avg win:        {result.avg_win}")
    print(f"Avg loss:       {result.avg_loss}")
    print(f"Expectancy:     {result.expectancy}")


def main():
    # Candidata principal
    run_candidate(
        name="SELL_8_14_ADX30_38_RR1.2_SL1.2",
        rr_ratio=1.2,
        atr_sl_mult=1.2,
    )

    # Candidata secundaria
    run_candidate(
        name="SELL_8_14_ADX30_38_RR1.4_SL1.0",
        rr_ratio=1.4,
        atr_sl_mult=1.0,
    )


if __name__ == "__main__":
    main()