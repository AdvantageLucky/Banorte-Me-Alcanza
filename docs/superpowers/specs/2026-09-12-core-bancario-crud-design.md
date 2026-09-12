# Diseño: CRUD del core bancario simulado — me-alcanza

## Objetivo

Exponer, vía el backend, las operaciones de gestión que hoy no existen
sobre los datos del "core bancario" simulado: contactos, gastos fijos,
ingresos programados, metas y apartados. Estas operaciones son
consumidas de dos formas:

1. **REST directo** — nuevos endpoints en `/api/...` para que un
   frontend (la pestaña "Yo" de Flutter, en un sub-proyecto
   posterior) construya pantallas de formularios CRUD normales, sin
   pasar por el LLM.
2. **Chat/LLM** — el modelo ya puede *leer* estas entidades hoy
   (`_READ_ONLY_TOOLS` ya incluye `get_ingresos_programados`,
   `get_gastos_fijos`, `get_metas`, `buscar_contacto`); este spec
   agrega la capacidad de **proponer creaciones** nuevas
   conversacionalmente (ej. "agrégame una meta de ahorro para
   vacaciones"), siguiendo el mismo patrón de seguridad ya establecido
   para transferencias y apartados.

## Nota de arquitectura (para la presentación)

Todo lo nuevo son herramientas del servidor MCP `core-bancario`
(`mcp_bank/server.py` + `db.py`) — el backend **nunca** toca SQLite
directo, solo habla con el MCP vía `BankMcpClient`. Esto no cambia con
este spec: es el mismo patrón que ya existe para `get_saldo`,
`ejecutar_transferencia`, etc.

Conceptualmente, el servidor MCP juega el papel de "la API del banco":
en un sistema real, esto sería un servicio bancario interno (REST o
gRPC) que el backend consumiría como un cliente más. Aquí se simula
como un servidor MCP porque así lo pide el reto — pero el backend no
sabe ni le importa cómo está implementado el "banco" del otro lado,
solo conoce el contrato de sus herramientas. Vale la pena remarcar esta
distinción en la presentación: la arquitectura ya está preparada para
que "core bancario" sea, mañana, un servicio real sin tocar el backend.

## Alcance

**Incluido en este sub-proyecto (backend):**

- Nuevas funciones en `db.py` y nuevas `@mcp.tool()` en `server.py`
  para las operaciones de escritura que faltan (ver tabla abajo).
- Nuevos endpoints REST en `routes.py` + nuevos DTOs en `dtos.py`.
- Nuevas herramientas `proponer_X` (backend-local, no mutan nada) +
  nuevas ramas en `confirm_action` para las 4 entidades cuya creación
  se puede proponer por chat.
- Tests (TDD) para cada operación nueva en `db.py`/`server.py`/rutas,
  incluyendo casos de ownership y las reglas de negocio abajo.

**Fuera de alcance (explícitamente, para no diluir este sub-proyecto):**

- Las pantallas Flutter de la pestaña "Yo" que consuman esta API —
  sub-proyecto separado, spec+plan propios, después de que esto esté
  mergeado.
- Cualquier cambio al frontend React.
- Editar/borrar contactos, gastos fijos, ingresos programados o metas
  **vía chat** — eso es exclusivo de REST/Flutter (evita la ambigüedad
  de lenguaje natural sobre "cuál registro específico" tocar).
- CRUD sobre `movimientos` (solo lectura: es el libro mayor, se genera
  solo desde otras operaciones) y sobre `cuentas` (solo lectura: el
  saldo siempre es derivado de operaciones, nunca editable a mano).
- Edición del monto/periodicidad de un apartado ya activo (solo se
  puede cancelar) y edición directa de `metas.monto_ahorrado` (siempre
  derivado de apartados).

## Alcance por entidad

| Entidad | REST | Chat (LLM) |
|---|---|---|
| `cuentas` | GET | ya existe (`get_cuenta`, solo lectura) |
| `movimientos` | GET (`?limit=`) | ya existe (`get_movimientos`, solo lectura) |
| `contactos` | GET, POST, PATCH, DELETE | ya lee (`buscar_contacto`) + **proponer creación nueva** |
| `ingresos_programados` | GET, POST, PATCH, DELETE | ya lee (`get_ingresos_programados`) + **proponer creación nueva** |
| `gastos_fijos` | GET, POST, PATCH, DELETE | ya lee (`get_gastos_fijos`) + **proponer creación nueva** |
| `metas` | GET, POST, PATCH, DELETE | ya lee (`get_metas`) + **proponer creación nueva** |
| `apartados` | GET (listar), POST (crear), POST `/cancelar` | ya existe `proponer_apartado`/creación; cancelar es solo REST |

Reglas de negocio específicas:

- **`metas`**: DELETE se bloquea (error, mapeado a 400 como el resto —
  ver más abajo) si la meta tiene algún apartado con `estado='activo'`
  apuntándole. `monto_ahorrado` nunca es parte de los DTOs de
  create/update — es siempre derivado.
- **`apartados`**: no existe edición de `monto_por_periodo`/
  `periodicidad` de uno activo. Cancelar solo cambia `estado` a
  `'cancelado'` — no hay reintegro automático de saldo (el sistema no
  tiene un job que ejecute periodos futuros automáticamente; solo se
  descontó el primer periodo al crearlo, así que cancelar simplemente
  detiene el compromiso, sin mover dinero).
- **Ownership**: toda operación de update/delete/cancelar valida que
  el registro pertenezca al `account_id` del JWT antes de tocarlo —
  mismo patrón que `get_contacto` ya usa hoy.

## Herramientas MCP nuevas

En `db.py` + `server.py` (todas reciben/validan `account_id`):

```
crear_contacto(account_id, nombre, alias, cuenta_destino, relacion) -> dict
actualizar_contacto(account_id, contacto_id, nombre, alias, cuenta_destino, relacion) -> dict
eliminar_contacto(account_id, contacto_id) -> dict

crear_ingreso_programado(account_id, descripcion, monto, frecuencia, proxima_fecha) -> dict
actualizar_ingreso_programado(account_id, ingreso_id, descripcion, monto, frecuencia, proxima_fecha) -> dict
eliminar_ingreso_programado(account_id, ingreso_id) -> dict

crear_gasto_fijo(account_id, concepto, monto, frecuencia, proxima_fecha) -> dict
actualizar_gasto_fijo(account_id, gasto_id, concepto, monto, frecuencia, proxima_fecha) -> dict
eliminar_gasto_fijo(account_id, gasto_id) -> dict

crear_meta(account_id, descripcion, monto_objetivo, fecha_objetivo) -> dict
actualizar_meta(account_id, meta_id, descripcion, monto_objetivo, fecha_objetivo) -> dict
eliminar_meta(account_id, meta_id) -> dict  # ValueError si tiene apartados activos

listar_apartados(account_id) -> list[dict]
cancelar_apartado(account_id, apartado_id) -> dict  # estado -> 'cancelado'
```

`listar_contactos` no hace falta: `buscar_contacto(account_id, "")` ya
devuelve todos (el `LIKE '%%'` matchea todo) — se reutiliza tal cual
para el `GET /api/contactos`.

Ninguna de estas tools nuevas se agrega a `_READ_ONLY_TOOLS` ni a
`read_only_tool_declarations()` — el LLM nunca las ve ni las puede
llamar directo. Las 4 `crear_X` sí se usan desde dos lugares: el
endpoint REST `POST` correspondiente, y la rama de `confirm_action`
para su `proponer_X` (mismo código, sin duplicar lógica).

## Nuevas herramientas conversacionales (`proponer_X`)

Mismo patrón que `proponer_transferencia`/`proponer_apartado`: reciben
`account_id` + args del LLM, validan, crean una `Proposal` en memoria
(`proposals.crear_propuesta`), devuelven `{proposalId, resumen}` al
modelo — **nunca tocan la base de datos**. Solo cubren creación:

```
proponer_contacto(nombre, alias, cuenta_destino, relacion)
proponer_gasto_fijo(concepto, monto, frecuencia, proxima_fecha)
proponer_ingreso_programado(descripcion, monto, frecuencia, proxima_fecha)
proponer_meta(descripcion, monto_objetivo, fecha_objetivo)
```

`confirm_action` gana 4 ramas nuevas (`proposal.tipo ==
"contacto"/"gasto_fijo"/"ingreso_programado"/"meta"`), cada una
llamando a su `crear_X` de MCP y devolviendo un bloque de confirmación
A2UI, igual que las 2 ramas existentes.

`build_system_prompt()` gana instrucciones en `workflow_description`
explicando cuándo usar cada `proponer_X` (ej. "si el usuario menciona
un gasto recurrente nuevo que no está en `get_gastos_fijos`, usa
`proponer_gasto_fijo`... nunca lo des por creado hasta que el usuario
confirme").

## Endpoints REST nuevos

```
GET    /api/cuenta
GET    /api/movimientos?limit=10

GET    /api/contactos
POST   /api/contactos
PATCH  /api/contactos/{contacto_id}
DELETE /api/contactos/{contacto_id}

GET    /api/ingresos-programados
POST   /api/ingresos-programados
PATCH  /api/ingresos-programados/{ingreso_id}
DELETE /api/ingresos-programados/{ingreso_id}

GET    /api/gastos-fijos
POST   /api/gastos-fijos
PATCH  /api/gastos-fijos/{gasto_id}
DELETE /api/gastos-fijos/{gasto_id}

GET    /api/metas
POST   /api/metas
PATCH  /api/metas/{meta_id}
DELETE /api/metas/{meta_id}

GET    /api/apartados
POST   /api/apartados
POST   /api/apartados/{apartado_id}/cancelar
```

Todas usan `Depends(auth.get_current_account_id)` — el `account_id`
siempre viene del JWT, igual que las 3 rutas existentes. `POST`
responde 201, `DELETE`/`cancelar` responde 200 con el recurso
actualizado (o 204 para `DELETE`), `GET`/`PATCH` responden 200.

## DTOs

Un `Create`, un `Update` (mismos campos, todos opcionales — PATCH
parcial) y un `Response` por entidad mutable. Ejemplo (`gastos_fijos`):

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

Frecuencia = Literal["semanal", "quincenal", "mensual", "anual"]

class GastoFijoCreate(BaseModel):
    concepto: str
    monto: float = Field(gt=0)
    frecuencia: Frecuencia
    proxima_fecha: date

class GastoFijoUpdate(BaseModel):
    concepto: str | None = None
    monto: float | None = Field(default=None, gt=0)
    frecuencia: Frecuencia | None = None
    proxima_fecha: date | None = None

class GastoFijoResponse(BaseModel):
    id: int
    concepto: str
    monto: float
    frecuencia: str
    proxima_fecha: str
```

`frecuencia`/`periodicidad` es hoy texto libre en el schema (nada lo
interpreta semánticamente — `cashflow.py` solo usa `proxima_fecha`
como una única ocurrencia dentro de la ventana simulada). Se restringe
a un enum de 4 valores en los DTOs porque da mejor UI en Flutter
(dropdown en vez de texto libre) sin costo real; la columna SQL sigue
siendo `TEXT`, no hace falta migración.

Estructura análoga para `ContactoCreate/Update/Response`,
`IngresoProgramadoCreate/Update/Response`, `MetaCreate/Update/Response`
(sin `monto_ahorrado` en Create/Update), y `ApartadoResponse` (solo
lectura — se crea con un DTO propio `ApartadoCreate {meta_id,
monto_por_periodo, periodicidad}` que reusa `crear_apartado`).

## Manejo de errores (simplificación consciente)

El límite MCP hoy colapsa cualquier excepción de una tool (`ValueError`
u otra) en un `RuntimeError` genérico con el mensaje como texto —no
hay código de error tipado cruzando el protocolo MCP (mismo patrón que
`login`/`confirm_action` ya usan). Las rutas nuevas siguen esta misma
convención: cualquier `RuntimeError` capturado desde `BankMcpClient`
se traduce a `HTTPException(400, detail=str(exc))`. Esto cubre "no
encontrado", "no te pertenece" y "meta con apartados activos" con el
mismo mecanismo — no es 100% REST-idiomático (un "no encontrado"
debería ser 404) pero es consistente con el resto del código y evita
tocar la plomería del protocolo MCP, que es una decisión de
infraestructura más grande y fuera de alcance aquí.

## Testing

Mismo patrón ya usado en el repo:

- `tests/mcp_bank/test_db.py` / `test_server.py`: cada función/tool
  nueva, incluyendo ownership (no puedes tocar un registro de otra
  cuenta) y el bloqueo de borrado de meta con apartados activos.
- `tests/backend/test_routes.py`: cada endpoint nuevo, con
  `BankMcpClient` mockeado — status codes, DTOs, propagación de
  errores.
- `tests/backend/test_orchestrator.py`: cada `proponer_X` nuevo (args
  faltantes, feliz camino) y cada rama nueva de `confirm_action`
  (incluyendo que la propuesta se descarta antes de ejecutar, como ya
  se prueba para apartado/transferencia).

TDD en todos los casos: test primero, ver fallar, implementar mínimo,
ver pasar.
