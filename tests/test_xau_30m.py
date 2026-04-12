import pandas as pd
df = pd.read_csv("backtest/data/XAUUSD_30M.csv", index_col=0, parse_dates=True)
df.columns = [c.lower() for c in df.columns]
hl  = df['high'] - df['low']
hcp = (df['high'] - df['close'].shift()).abs()
lcp = (df['low']  - df['close'].shift()).abs()
atr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(14).mean()
print(f"ATR 30M promedio: {atr.mean():.4f}")
print(f"Precio promedio:  {df['close'].mean():.4f}")
print(df.head(3))