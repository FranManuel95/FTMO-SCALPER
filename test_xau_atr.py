import MetaTrader5 as mt5
import pandas as pd

mt5.initialize()
r = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_M5, 0, 200)
df = pd.DataFrame(r)
hl  = df['high'] - df['low']
hcp = (df['high'] - df['close'].shift()).abs()
lcp = (df['low']  - df['close'].shift()).abs()
atr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(14).mean()
print(f"ATR XAUUSD M5 promedio : {atr.mean():.4f}")
print(f"ATR XAUUSD M5 actual   : {atr.iloc[-1]:.4f}")
print(f"Precio actual          : {df['close'].iloc[-1]:.2f}")

# Ver también EMAs
close = df['close']
print(f"EMA1  : {close.ewm(span=1,  adjust=False).mean().iloc[-1]:.2f}")
print(f"EMA14 : {close.ewm(span=14, adjust=False).mean().iloc[-1]:.2f}")
print(f"EMA18 : {close.ewm(span=18, adjust=False).mean().iloc[-1]:.2f}")
print(f"EMA24 : {close.ewm(span=24, adjust=False).mean().iloc[-1]:.2f}")
print(f"EMA200: {close.ewm(span=200, adjust=False).mean().iloc[-1]:.2f}")
mt5.shutdown()