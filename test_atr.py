import MetaTrader5 as mt5
import pandas as pd

mt5.initialize()
rates = mt5.copy_rates_from_pos("USDJPY", mt5.TIMEFRAME_M5, 0, 100)
df = pd.DataFrame(rates)
hl  = df['high'] - df['low']
hcp = (df['high'] - df['close'].shift()).abs()
lcp = (df['low']  - df['close'].shift()).abs()
atr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(14).mean()
print(f"ATR USDJPY M5 promedio: {atr.mean():.5f}")
print(f"ATR USDJPY M5 actual:   {atr.iloc[-1]:.5f}")
mt5.shutdown()