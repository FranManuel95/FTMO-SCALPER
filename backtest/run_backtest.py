from backtest.backtester     import FTMOBacktester
from backtest.backtester_gbp import GBPBacktester
from backtest.backtester_xau import XAUBacktester

# === EURUSD Grid Search ===
# print("\n=== EURUSD - Optimizacion ===")
# bt1 = FTMOBacktester(10000)
# result1 = bt1.run()         
# result1.print_report()

# # === GBPUSD Grid Search ===
# print("\n=== GBPUSD - Optimizacion ===")
# bt2 = GBPBacktester(10000)
# result2 = bt2.run()
# result2.print_report()

# === XAUUSD con params actuales ===
print("\n=== XAUUSD - SuperTrend H1 ===")
bt3 = XAUBacktester(10000)
result3 = bt3.run()
result3.print_report()