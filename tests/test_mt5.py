import MetaTrader5 as mt5

# Inicializar conexion
if not mt5.initialize():
    print(f"Error al inicializar MT5: {mt5.last_error()}")
    quit()

# Info de la cuenta
account = mt5.account_info()
print(f"Conectado: {account.login}")
print(f"Broker: {account.company}")
print(f"Balance: ${account.balance}")
print(f"Equity: ${account.equity}")
print(f"Servidor: {account.server}")

# Probar velas M5
import pandas as pd
rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M5, 0, 10)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print(f"\nUltimas 10 velas M5:")
print(df[['time', 'open', 'high', 'low', 'close']].to_string())

mt5.shutdown()
print("\nConexion MT5 OK")