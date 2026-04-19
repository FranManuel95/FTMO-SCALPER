# Visión del Proyecto

## Objetivo principal

Construir un sistema donde cada nueva idea de estrategia siga este camino:

```
idea → spec → research → backtest → validación → reporte → decisión
```

Y donde se reutilicen:
- features técnicas
- filtros de riesgo
- métricas de evaluación
- prompts y skills de IA
- conectores MCP

Sin rehacer el trabajo cada vez.

## Lo que este proyecto NO es

- Un bot de trading automático listo para operar
- Una colección de repos sin cohesión
- Un sistema que depende de indicadores "mágicos"
- Un framework sobreingenierizado antes de probar edge real

## Principios de diseño

1. **Modularidad** — cada pieza tiene un rol claro y se puede usar independientemente
2. **Reutilización** — features, filtros y métricas son compartidos entre estrategias
3. **Honestidad estadística** — nada pasa sin validación IS/OOS y stress test
4. **Fondeo-first** — las reglas FTMO son constraints desde el día 1, no parches finales
5. **IA como filtro** — la IA mejora robustez, no reemplaza lógica

## Roles de cada componente

| Componente | Rol |
|---|---|
| LEAN/QuantConnect | Framework principal: estrategias forex/metales/crypto serias |
| Freqtrade | Laboratorio crypto: dry-run, optimización rápida, FreqAI |
| ML for Trading | Metodología: features, clasificación de régimen, señales |
| MCP tools | Productividad: research asistido, generación de código |
| Skills | Workflows repetibles: spec, review, compare, convert |
