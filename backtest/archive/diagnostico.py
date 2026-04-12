import pandas as pd
import numpy as np

df = pd.read_csv("backtest/data/EURUSD_M5.csv", index_col=0, parse_dates=True)
df.columns = [c.lower() for c in df.columns]
df = df.sort_index()

close = df['close']
df['ema_fast']  = close.ewm(span=9,   adjust=False).mean()
df['ema_slow']  = close.ewm(span=21,  adjust=False).mean()
df['ema_trend'] = close.ewm(span=200, adjust=False).mean()

delta = close.diff()
gain  = delta.where(delta > 0, 0).rolling(14).mean()
loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, 1e-10)))

hl  = df['high'] - df['low']
hcp = (df['high'] - close.shift()).abs()
lcp = (df['low']  - close.shift()).abs()
df['atr'] = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(14).mean()
df['hour'] = df.index.hour
df['session'] = (df['hour'] >= 7) & (df['hour'] < 17)
df = df.dropna()

# Contar señales por tipo de filtro
total_cruces    = 0
filtro_sesion   = 0
filtro_tendencia= 0
filtro_rsi      = 0
filtro_atr      = 0
filtro_estructura = 0
señales_validas = 0

for i in range(22, len(df) - 10):
    row      = df.iloc[i]
    prev_row = df.iloc[i - 1]

    prev_above = prev_row['ema_fast'] > prev_row['ema_slow']
    curr_above =      row['ema_fast'] >      row['ema_slow']
    bullish = (not prev_above) and curr_above
    bearish =      prev_above  and (not curr_above)

    if not (bullish or bearish): continue
    total_cruces += 1

    if not row['session']:
        filtro_sesion += 1
        continue

    curr_price = float(row['close'])
    curr_trend = float(row['ema_trend'])
    curr_atr   = float(row['atr'])

    if curr_atr < 0.0003:
        filtro_atr += 1
        continue

    if bullish and curr_price <= curr_trend:
        filtro_tendencia += 1
        continue
    if bearish and curr_price >= curr_trend:
        filtro_tendencia += 1
        continue

    curr_rsi = float(row['rsi'])
    if bullish and not (45 < curr_rsi < 65):
        filtro_rsi += 1
        continue
    if bearish and not (35 < curr_rsi < 55):
        filtro_rsi += 1
        continue

    if bullish:
        structure_high = float(df.iloc[i-5:i]['high'].max())
        if curr_price <= structure_high * 0.9995:
            filtro_estructura += 1
            continue
    else:
        structure_low = float(df.iloc[i-5:i]['low'].min())
        if curr_price >= structure_low * 1.0005:
            filtro_estructura += 1
            continue

    señales_validas += 1

print("\n--- DIAGNOSTICO DE FILTROS ---")
print(f"Total cruces EMA          : {total_cruces}")
print(f"Filtrados por sesion      : {filtro_sesion}")
print(f"Filtrados por ATR bajo    : {filtro_atr}")
print(f"Filtrados por tendencia   : {filtro_tendencia}")
print(f"Filtrados por RSI         : {filtro_rsi}")
print(f"Filtrados por estructura  : {filtro_estructura}")
print(f"Senales validas           : {señales_validas}")
print(f"Tasa de filtrado          : {(1 - señales_validas/max(total_cruces,1))*100:.1f}%")