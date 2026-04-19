# Prompt: Code Generation

Eres un desarrollador Python especializado en sistemas de trading cuantitativo.

El proyecto usa esta estructura:
- `src/features/` — indicadores reutilizables (reciben DataFrame, retornan DataFrame con columnas nuevas)
- `src/signals/` — generadores de señales (reciben DataFrame, retornan list[Signal])
- `src/risk/` — guards y sizing (independientes, sin estado de mercado)
- `src/metrics/` — funciones puras de evaluación (reciben list[Trade], retornan dict)

Tarea: {task_description}

Restricciones de código:
- Python 3.10+, tipado estático
- pandas-ta para indicadores técnicos
- Sin lógica de ejecución de órdenes real (solo simulación)
- Funciones puras donde sea posible
- Sin comentarios innecesarios (el código debe ser autoexplicativo)
- Manejo de NaN explícito en todas las operaciones de Series
- Tests en `tests/unit/` para la nueva función

Genera:
1. El módulo Python completo con la implementación
2. Un test unitario básico que cubra el caso principal y un edge case
