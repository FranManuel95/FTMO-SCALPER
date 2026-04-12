import pandas as pd

from backtest.backtester_gbp import GBPBacktester


def run_period(name: str, start_date: str, end_date: str):
    print(f"\n{'=' * 80}")
    print(f"SUBPERIODO: {name} | {start_date} -> {end_date}")
    print(f"{'=' * 80}")

    bt = GBPBacktester(
        initial_balance=10000,
        risk_per_trade=0.005,
        rr_ratio=1.4,
        atr_sl_mult=1.0,
        symbol="GBPUSD",
        export_trades=False,
        session_start=8,
        session_end=14,
        adx_min=30,
        adx_max=38,
        trade_mode="SELL_ONLY",
    )

    df = bt.load_data()
    df = df.loc[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))].copy()

    if df.empty:
        raise ValueError(f"Sin datos para el rango {start_date} -> {end_date}")

    # Monkey patch simple para reutilizar el backtester sin duplicar lógica
    bt.load_data = lambda: df

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

    return {
        "period": name,
        "start_date": start_date,
        "end_date": end_date,
        "trades": result.total_trades,
        "win_rate": round(result.win_rate * 100, 2),
        "profit_factor": result.profit_factor,
        "sharpe": result.sharpe_ratio,
        "sortino": result.sortino_ratio,
        "max_dd_pct": round(result.max_drawdown * 100, 2),
        "total_return_pct": round(result.total_return * 100, 2),
        "avg_win": result.avg_win,
        "avg_loss": result.avg_loss,
        "expectancy": result.expectancy,
    }


def main():
    periods = [
        ("P1_FIRST_BLOCK", "2024-11-01", "2025-03-31"),
        ("P2_MIDDLE_BLOCK", "2025-04-01", "2025-08-31"),
        ("P3_LAST_BLOCK", "2025-09-01", "2026-04-09"),
        ("H1_FIRST_HALF", "2024-11-01", "2025-07-15"),
        ("H2_SECOND_HALF", "2025-07-16", "2026-04-09"),
    ]

    results = []

    for name, start_date, end_date in periods:
        try:
            row = run_period(name, start_date, end_date)
            results.append(row)
        except Exception as e:
            print(f"\nERROR en {name}: {e}")

    if not results:
        raise ValueError("No hubo resultados válidos.")

    out_df = pd.DataFrame(results)

    print(f"\n{'=' * 80}")
    print("RESUMEN GLOBAL SUBPERIODOS")
    print(f"{'=' * 80}")
    print(out_df.to_string(index=False))


if __name__ == "__main__":
    main()