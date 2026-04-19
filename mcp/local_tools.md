# MCP — Herramientas Locales

## Filesystem MCP

Permite a Claude acceder a los archivos del proyecto directamente:

```json
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/ruta/al/proyecto"]
  }
}
```

Útil para:
- Revisar resultados de backtest automáticamente
- Leer configuraciones y specs
- Generar reportes
- Analizar notebooks

## Posibles herramientas locales a desarrollar

### tool: run_backtest
Lanza un backtest y retorna el resultado en JSON.

### tool: get_strategy_metrics
Retorna métricas de una estrategia guardada.

### tool: list_experiments
Lista todos los experimentos guardados en `reports/`.

### tool: check_ftmo_rules
Verifica si un resultado pasa los checks FTMO.

Estas herramientas se implementarían como un servidor MCP local
usando el SDK de MCP de Python o Node.js.
