# backtest/run_mtf.py — Runner MTF: EURUSD + GBPUSD
#
# Ejecutar: python -m backtest.run_mtf
#
# Corre el backtest MTF en ambos pares y muestra:
#   1. Métricas individuales por par
#   2. Resumen mensual
#   3. Breakdown de tipo de entrada (CROSSOVER vs PULLBACK)
#   4. Resultado combinado del portfolio

from pathlib import Path
import pandas as pd
from backtest.backtester_mtf import MTFBacktester


SYMBOLS = ["EURUSD", "GBPUSD"]


def run_symbol(symbol: str) -> dict:
    bt = MTFBacktester(
        symbol=symbol,
        initial_balance=10_000,
        risk_per_trade=0.005,
    )
    result = bt.run()

    print(f"\n{'='*60}")
    print(f"  {symbol} — MTF (H1 bias + 15M setup + 5M entrada)")
    print(f"{'='*60}")
    print(f"  Total trades  : {result.total_trades}")
    print(f"  Win rate      : {result.win_rate:.2%}")
    print(f"  Profit factor : {result.profit_factor:.3f}  (mín 1.3)")
    print(f"  Sharpe        : {result.sharpe_ratio:.3f}  (mín 1.5)")
    print(f"  Max drawdown  : {result.max_drawdown:.2%}  (máx 8%)")
    print(f"  Total return  : {result.total_return:.2%}")
    print(f"  Avg win       : ${result.avg_win:.2f}")
    print(f"  Avg loss      : ${result.avg_loss:.2f}")
    print(f"  Expectancy    : ${result.expectancy:.2f}")

    if hasattr(result, "extra_stats") and result.extra_stats:
        es    = result.extra_stats
        total = max(sum(es.values()), 1)
        print(f"\n  Salidas:")
        for k, v in es.items():
            print(f"    {k:8s}: {v:4d}  ({v/total:.1%})")

    if bt.last_trades_detail:
        trades_df = pd.DataFrame(bt.last_trades_detail)
        trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])

        # Guardar CSV
        out = Path("backtest/results")
        out.mkdir(parents=True, exist_ok=True)
        trades_df.to_csv(out / f"mtf_{symbol.lower()}_trades.csv", index=False)

        # Resumen mensual
        trades_df["month"] = trades_df["entry_time"].dt.to_period("M").astype(str)
        monthly = (
            trades_df.groupby("month")
            .agg(
                trades  =("pnl", "count"),
                wins    =("won", lambda s: int(s.sum())),
                pnl     =("pnl", "sum"),
                tp      =("exit_reason", lambda s: int((s == "tp").sum())),
                sl      =("exit_reason", lambda s: int((s == "sl").sum())),
                be      =("exit_reason", lambda s: int((s == "be").sum())),
                timeout =("exit_reason", lambda s: int((s == "timeout").sum())),
                cross   =("mode", lambda s: int((s == "CROSS").sum())),
                pull    =("mode", lambda s: int((s == "PULL").sum())),
            )
            .reset_index()
        )
        monthly["wr"] = (monthly["wins"] / monthly["trades"]).round(3)
        monthly["pnl"] = monthly["pnl"].round(2)

        print(f"\n  Resumen mensual:")
        print(monthly.to_string(index=False))

        # Breakdown por modo de entrada
        if "mode" in trades_df.columns:
            print(f"\n  Breakdown por modo:")
            mode_grp = trades_df.groupby("mode").agg(
                trades =("pnl", "count"),
                wr     =("won", "mean"),
                pnl    =("pnl", "sum"),
            ).round(3)
            print(mode_grp.to_string())

    ftmo_ok = (
        result.win_rate       >= 0.45 and
        result.profit_factor  >= 1.30 and
        result.max_drawdown   <= 0.08
    )
    print(f"\n  FTMO: {'✓ APROBADO' if ftmo_ok else '✗ RECHAZADO'}")

    return {
        "symbol": symbol,
        "trades": result.total_trades,
        "wr":     result.win_rate,
        "pf":     result.profit_factor,
        "sharpe": result.sharpe_ratio,
        "dd":     result.max_drawdown,
        "ret":    result.total_return,
        "detail": bt.last_trades_detail,
    }


def main():
    results = []
    all_trades = []

    for sym in SYMBOLS:
        r = run_symbol(sym)
        results.append(r)
        all_trades.extend(r["detail"])

    # ── Portfolio combinado ──────────────────────────────────────────────
    if all_trades:
        print(f"\n{'='*60}")
        print("  PORTFOLIO COMBINADO (EURUSD + GBPUSD)")
        print(f"{'='*60}")

        df_all = pd.DataFrame(all_trades)
        df_all["entry_time"] = pd.to_datetime(df_all["entry_time"])
        df_all = df_all.sort_values("entry_time")

        total_trades = len(df_all)
        total_wr     = df_all["won"].mean()
        total_pnl    = df_all["pnl"].sum()

        # Equity curve combinada
        balance = 10_000
        eq = [balance]
        for pnl in df_all["pnl"]:
            balance += pnl
            eq.append(balance)
        import numpy as np
        eq_arr = np.array(eq)
        peak   = np.maximum.accumulate(eq_arr)
        max_dd = float(np.max((peak - eq_arr) / (peak + 1e-10)))

        wins   = df_all[df_all["pnl"] > 0]["pnl"].sum()
        losses = abs(df_all[df_all["pnl"] < 0]["pnl"].sum())
        pf     = wins / (losses + 1e-10)

        print(f"  Total trades  : {total_trades}")
        print(f"  Win rate      : {total_wr:.2%}")
        print(f"  Profit factor : {pf:.3f}")
        print(f"  Max drawdown  : {max_dd:.2%}")
        print(f"  Total P&L     : ${total_pnl:.2f}")
        print(f"  Trades/mes    : {total_trades / (len(df_all['entry_time'].dt.to_period('M').unique())):.1f}")

        # Días de trading únicos
        trading_days = df_all["entry_time"].dt.date.nunique()
        print(f"  Días con trades: {trading_days}")
        print(f"  FTMO mín 10 días: {'✓' if trading_days >= 10 else '✗'} ({trading_days} días)")


if __name__ == "__main__":
    main()
