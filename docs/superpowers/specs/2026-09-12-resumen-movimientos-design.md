# Diseño: Canal separado de datos — el LLM solo ve agregados de movimientos

## Objetivo

Hoy la tool MCP `get_movimientos` (fecha/concepto/monto por transacción) está
expuesta directo al LLM. Este spec la reemplaza por una tool de agregados
(`get_resumen_movimientos`), dejando el detalle crudo exclusivamente en el
canal REST directo (`GET /api/movimientos`, ya construido en el CRUD del core
bancario, sin cambios) que Flutter/React consumen sin pasar por el LLM.

## Alcance

**Incluido:** columna `categoria` en `movimientos` (con migración segura para
DBs ya existentes), asignación de categoría por código en las dos funciones
que ya insertan movimientos (`ejecutar_transferencia`, `crear_apartado`), tool
MCP nueva `get_resumen_movimientos`, retiro de `get_movimientos` del catálogo
del LLM, actualización del `workflow_description`.

**Fuera de alcance:** `cuenta_destino` de contactos sigue expuesto al LLM tal
cual (decisión explícita: rediseñar `proponer_transferencia` para ocultarlo
es una iteración futura, no rompe nada urgente hoy). Ningún cambio a
`GET /api/movimientos` ni a los DTOs REST existentes.

## Categorización — por código, no por texto libre

`concepto` es texto libre (ej. "Transferencia recibida: Pago de renta"),
poco confiable para clasificar por keywords. En vez de inferir, cada función
que inserta un movimiento pasa su propia categoría fija, conocida en el
momento de la inserción — cero ambigüedad:

| Función | Inserción | `categoria` |
|---|---|---|
| `ejecutar_transferencia` | fila de la cuenta origen | `"transferencia_enviada"` |
| `ejecutar_transferencia` | fila de la cuenta destino (si existe internamente) | `"transferencia_recibida"` |
| `crear_apartado` | fila del apartado | `"ahorro"` |

Estas son las únicas 3 categorías posibles con el código actual. La columna
lleva `DEFAULT 'otro'` como red de seguridad para cualquier fila futura que no
pase por estas dos funciones (hoy no existe ese caso).

## Migración de schema

`movimientos` ya tiene datos persistidos (local y homelab) — `CREATE TABLE IF
NOT EXISTS` no altera una tabla que ya existe. `db.get_connection` ejecuta,
tras crear el schema base, un `ALTER TABLE movimientos ADD COLUMN categoria
TEXT NOT NULL DEFAULT 'otro'` envuelto en `try/except sqlite3.OperationalError:
pass` (SQLite no soporta `ADD COLUMN IF NOT EXISTS`; el error de "duplicate
column" es la señal de que ya se migró). Segura de correr en cada arranque,
en DBs nuevas y viejas por igual.

## Tool MCP nueva

```
get_resumen_movimientos(account_id, fecha_inicio, fecha_fin) -> list[dict]
```

Devuelve `[{"categoria": str, "total": float, "count": int}, ...]` — suma y
conteo de movimientos por categoría dentro del rango de fechas (inclusive),
usando `SUM(monto)`/`COUNT(*)` con `GROUP BY categoria`. `total` conserva el
signo (positivo = ingreso, negativo = egreso), consistente con `monto` en
`movimientos`.

## Cambios en `orchestrator.py`

- `get_movimientos` sale de `_READ_ONLY_TOOLS` y de
  `read_only_tool_declarations()` — el LLM ya no puede llamarla.
- Entra `get_resumen_movimientos` a ambos, con `fecha_inicio`/`fecha_fin`
  como argumentos requeridos tipo `STRING` (formato `YYYY-MM-DD`).
- `workflow_description` gana una instrucción: para preguntas sobre patrones
  de gasto ("¿en qué gasté este mes?"), usa `get_resumen_movimientos` con un
  rango que tú mismo calculas a partir de la fecha de hoy (ej. "este mes" =
  del día 1 del mes actual a hoy); nunca pidas movimiento por movimiento.

## Testing

Mismo patrón del proyecto: tests de `db.py` (migración idempotente, cálculo
de agregados con datos sembrados vía `ejecutar_transferencia`/
`crear_apartado`), tests de `server.py` (tool nueva vía stdio real, tool
vieja ya no en el set esperado), tests de `orchestrator.py` (LLM ya no puede
llamar `get_movimientos`, sí puede llamar y recibir bien
`get_resumen_movimientos`).

## Nota para quien ejecute este plan

Este spec fue diseñado en una sesión con tiempo de hackathon limitado —
las decisiones de alcance (excluir `cuenta_destino`, agrupar por categoría
fija de 3 valores) están tomadas explícitamente para mantener esto pequeño y
enviable. Si hay tiempo de sobra, discutan en equipo si vale la pena
extender el alcance antes de empezar.
