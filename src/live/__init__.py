"""
Live trading module — conecta el research lab a MT5 para ejecución automática.

Arquitectura:
  mt5_client       → wrapper sobre MetaTrader5 con inicialización/reconexión
  live_data_loader → devuelve DataFrames OHLCV compatibles con los signal generators
  order_manager    → place / modify / close orders con validación FTMO
  trail_manager    → actualiza SL de posiciones abiertas cada barra (ATR × mult)
  portfolio_runner → loop principal que orquesta N estrategias simultáneas
  strategy_state   → deduplicación de señales entre barras

Modo dry-run (default): las órdenes se simulan en logs, no se envían a MT5.
Modo live: las órdenes se envían al broker. Usar solo tras validación en demo.
"""
