# MCP y Skills

## Skills disponibles

| Skill | Input | Output |
|---|---|---|
| `generate_strategy_spec` | Idea de estrategia | Spec completa: hipótesis, reglas, parámetros |
| `review_backtest_results` | CSV/resumen backtest | Análisis: fortalezas, debilidades, siguiente paso |
| `compare_experiments` | Varios experimentos | Ranking, robustez, qué conservar |
| `build_feature_pipeline` | Ideas de features | Lista estructurada con advertencias de data leakage |
| `convert_idea_to_test_plan` | Intuición o setup | Plan de backtest: activos, TF, grid, métricas |

Ver archivos en `skills/` para los prompts completos.

## MCP — Servidores disponibles

### MCP Freqtrade (opcional)
Permite a un agente IA interactuar con el bot Freqtrade:
- Inspeccionar estado del bot
- Lanzar o revisar configuraciones
- Analizar estrategias
- Consultar resultados via API REST

Configuración: `mcp/freqtrade_mcp.md`

### MCP QuantConnect (opcional)
Conecta agentes con entorno QuantConnect/LEAN:
- Acelerar research
- Interacción con proyectos LEAN
- Revisión de algoritmos

Configuración: `mcp/quantconnect_mcp.md`

## Cómo usar IA de forma útil

### Sí — IA útil
- Clasificador de régimen de mercado (¿tendencia, rango, alta vol?)
- Filtro de setups buenos/malos (¿este setup tiene historial positivo?)
- Ranking de entradas (¿cuál es la entrada más probable de ser buena?)
- Selección de no-trade (¿cuándo NO entrar?)
- Adaptación conservadora de parámetros dentro de rangos robustos

### No — IA menos útil al principio
- Indicadores "mágicos" sin validación estadística
- LLM tomando decisiones directas de entrada/salida en tiempo real
- Hiperoptimización sin control de overfitting
- Reemplazar lógica de trading con predicciones de red neuronal

## Configuración de Claude Desktop

Ver `mcp/claude_desktop.example.json` para ejemplo de configuración.
