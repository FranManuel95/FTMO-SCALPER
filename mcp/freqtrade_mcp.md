# MCP — Freqtrade

## Qué permite

Con el MCP de Freqtrade un agente IA puede:
- Consultar el estado del bot (open trades, balance, profit)
- Revisar estrategias activas
- Lanzar o parar el bot
- Ver resultados de backtests recientes
- Analizar logs y errores

## Setup

1. Asegúrate de tener Freqtrade corriendo con la API habilitada:

```json
// en config.json
"api_server": {
    "enabled": true,
    "listen_ip_address": "127.0.0.1",
    "listen_port": 8080,
    "verbosity": "error",
    "enable_openapi": false,
    "jwt_secret_key": "your_secret",
    "CORS_origins": [],
    "username": "your_user",
    "password": "your_pass"
}
```

2. Instalar el MCP server:
```bash
pip install freqtrade-mcp
# o
uvx freqtrade-mcp
```

3. Configurar en `mcp/claude_desktop.example.json`

## Casos de uso en este proyecto

- Revisar resultados de dry-run automáticamente
- Comparar performance de estrategias en tiempo real
- Generar reportes desde resultados del bot
- Hacer preguntas al bot sobre trades abiertos
