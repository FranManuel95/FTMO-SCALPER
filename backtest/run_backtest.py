from backtest.backtester import FTMOBacktester

bt     = FTMOBacktester(10000)
result = bt.run()
result.print_report()