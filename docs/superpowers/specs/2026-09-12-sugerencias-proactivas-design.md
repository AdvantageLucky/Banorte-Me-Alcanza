# Diseño: Sugerencias proactivas (alertas sin chat) + historial

## Objetivo

Detectar automáticamente 3 situaciones financieras de riesgo usando reglas
deterministas (sin LLM en el camino de detección — inspirado en el patrón
"ShockAbsorber" de un equipo competidor del mismo reto: alertas que aparecen
solas, nunca requieren que el usuario le pregunte algo al chat), y llenar la
pestaña **Dashboard** (hoy placeholder) con un feed de sugerencias + su
historial (pendiente/atendida/descartada).

## Alcance

**Incluido:** tabla `sugerencias` nueva, 3 reglas de detección deterministas
sobre datos que YA existen en el schema, endpoints REST para listar/atender/
descartar, generación on-demand (sin cron — se recalcula cada vez que se
piden las sugerencias, con deduplicación).

**Fuera de alcance (explícitamente, para no inflar esto):** el LLM NO ve ni
genera estas sugerencias — es 100% determinista y ajeno al chat, coherente
con el punto de partida del concepto original ("sin chatbot"). Un motor de
detección de anomalías más sofisticado (series de tiempo, promedios
históricos reales) — nuestro schema no guarda historial de montos pasados
por gasto fijo, así que las 3 reglas de abajo usan solo lo que sí existe hoy.
Notificaciones push/tiempo real — el feed se consulta al cargar el Dashboard,
no hay push.

## Las 3 reglas de detección

Todas son funciones puras (mismo estilo que `cashflow.py`): reciben datos ya
consultados, devuelven una lista de sugerencias candidatas. Viven en un
archivo nuevo `src/me_alcanza/mcp_bank/sugerencias_engine.py`.

1. **`riesgo_liquidez`** — reusa `cashflow.simular_flujo_de_caja` tal cual
   existe hoy: para cada ingreso programado de la cuenta, simula con
   `fecha_objetivo = proxima_fecha` de ese ingreso y `monto_objetivo = 0`. Si
   `alcanza` es `False`, el saldo se proyecta negativo antes de la próxima
   quincena — se genera una sugerencia con el `margen` y la `fecha_critica`
   que la simulación ya calcula.
2. **`gasto_fijo_proximo`** — cualquier gasto fijo con `proxima_fecha` a 5
   días o menos de hoy Y `monto >= 30%` del saldo actual de la cuenta.
3. **`meta_en_riesgo`** — cualquier meta con `fecha_objetivo` a 30 días o
   menos de hoy Y `monto_ahorrado < monto_objetivo` (aún no completada).

Los umbrales (5 días, 30%, 30 días) son constantes en el módulo, fáciles de
ajustar — no hay ciencia detrás, son valores de demo razonables.

## Modelo de datos

```sql
CREATE TABLE IF NOT EXISTS sugerencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    tipo TEXT NOT NULL,               -- 'riesgo_liquidez' | 'gasto_fijo_proximo' | 'meta_en_riesgo'
    entidad_id TEXT NOT NULL,         -- id del gasto_fijo/meta relacionado, o el literal 'global' para riesgo_liquidez (NOT NULL a propósito: evita la semántica de NULL != NULL de SQL al deduplicar)
    detalle TEXT NOT NULL,            -- JSON con los datos específicos (montos, fechas) para renderizar
    estado TEXT NOT NULL DEFAULT 'pendiente',  -- 'pendiente' | 'atendida' | 'descartada'
    created_at TEXT NOT NULL,
    resuelta_at TEXT
);
```

## Generación on-demand con deduplicación

No hay infraestructura de cron en este proyecto — en vez de eso, cada
llamada a "listar sugerencias" primero corre las 3 reglas contra el estado
actual y **inserta solo las que no tengan ya una sugerencia `pendiente` del
mismo `tipo` + `entidad_id`** para esa cuenta (evita duplicar la misma
alerta en cada carga del Dashboard). Luego devuelve el listado completo
(pendientes + históricas) ordenado por `created_at DESC`.

## Endpoints REST nuevos

```
GET  /api/sugerencias                    -- genera + devuelve todas (con ?estado= opcional para filtrar)
POST /api/sugerencias/{id}/atender       -- estado -> 'atendida', resuelta_at = ahora
POST /api/sugerencias/{id}/descartar     -- estado -> 'descartada', resuelta_at = ahora
```

Mismo patrón que el resto del proyecto: `Depends(auth.get_current_account_id)`,
`RuntimeError -> HTTPException(400)`.

## Fuera del chat, dentro del mismo backend

Estas tools de detección **no se agregan a `_READ_ONLY_TOOLS` ni a
`read_only_tool_declarations()`** — el LLM no las ve, no las necesita, y
mantenerlas fuera evita cualquier riesgo de que el modelo "narre" una alerta
antes de que el usuario la vea en el Dashboard. Es consistente con el
espíritu del feature: proactivo pero determinista, nunca conversacional.

## Testing

Tests de `sugerencias_engine.py` (funciones puras, fixtures de datos
sintéticos por regla), tests de `db.py` (CRUD de la tabla + deduplicación),
tests de `server.py` (tools nuevas vía stdio), tests de `routes.py`
(endpoints REST, incluyendo que dos llamadas seguidas a `GET /api/sugerencias`
no dupliquen la misma alerta pendiente).

## Nota para quien ejecute este plan

Los umbrales de las 3 reglas (5 días, 30%, 30 días) son arbitrarios y
pensados para que la demo dispare alertas con los datos sembrados (`ana`
tiene una meta a 32 días y gastos fijos a 3-4 días — revisen si valen la
pena ajustar contra el seed real antes de grabar la demo). El feed del
Dashboard (cómo se ve, qué tan expandido el detalle) queda a discreción de
quien construya el frontend — este spec solo define el backend.
