import MetaTrader5 as mt5
import pandas as pd

mt5.initialize()
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 50)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

high = df['high']
low  = df['low']
close = df['close']
plus_dm  = high.diff().clip(lower=0)
minus_dm = (-low.diff()).clip(lower=0)
tr  = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
atr = tr.rolling(14).mean()
plus_di  = 100 * plus_dm.rolling(14).mean() / (atr + 1e-10)
minus_di = 100 * minus_dm.rolling(14).mean() / (atr + 1e-10)
dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
adx = dx.rolling(14).mean()

print(f"ADX actual 1H: {adx.iloc[-1]:.1f}")
print(f"EMA200: {close.ewm(span=200).mean().iloc[-1]:.5f}")
print(f"Precio actual: {close.iloc[-1]:.5f}")
mt5.shutdown()