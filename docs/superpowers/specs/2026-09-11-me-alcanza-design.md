# Diseño: me-alcanza — Asistente de flujo de caja con UI generativa

## Objetivo

Demo end-to-end para el reto "UI Generativa" (Banorte x Tec de Monterrey,
HackMTY 2026): un agente (LLM) que responde a preguntas de tipo *"me pagan
el día X, tengo estos compromisos entre hoy y la fecha Y, ¿me alcanza para Z?"*
armando la interfaz que resuelve el problema (proyección de flujo de caja,
veredicto, plan de apartado de ahorro), en vez de responder con texto plano.
Un segundo flujo (transferencia a un contacto, con desambiguación) demuestra
el mismo patrón de seguridad y de "hombre en el bucle" aplicado a un caso
distinto.

Cumple las tres piezas no negociables del reto:

- **LLM al centro**: interpreta intención, decide qué tools llamar y qué UI
  mostrar.
- **MCP**: servidor propio, dueño de la base de datos simulada (core
  bancario simulado), expone datos, herramientas y acciones.
- **A2UI**: protocolo usado para representar y transmitir la interfaz que
  arma el agente, con al menos un flujo accionable real (crear un apartado
  de ahorro o ejecutar una transferencia mueven dinero de verdad en la DB
  simulada).

Es una demo de hackathon acotada a un día, no un sistema productivo.

## Alcance

**Incluido:**

1. **Flujo núcleo — "¿me alcanza?"**: el usuario pregunta si le alcanza
   para un gasto discrecional futuro (ej. un concierto) dado su calendario
   de ingresos y gastos fijos ya conocidos por el sistema. El agente calcula
   la proyección de flujo de caja con una tool determinista, presenta un
   veredicto y, si hace falta, propone un plan de apartado de ahorro
   (monto y periodicidad) para llegar a la fecha sin descuadrar los pagos
   fijos. El usuario confirma y el apartado se crea de verdad (se reserva
   saldo real en la cuenta simulada).
2. **Flujo núcleo — transferencia con desambiguación**: el usuario pide
   transferir dinero a un contacto por nombre/apodo. Si el nombre es
   ambiguo (existe más de un contacto que calza), el agente muestra una
   lista de selección en vez de adivinar. Una vez resuelto el destino, se
   arma una tarjeta de confirmación explícita (monto, cuenta destino
   verificada, etiqueta de "propuesto por IA") y solo tras click del
   usuario se ejecuta la transferencia real.
3. **Contrato genérico de propuesta de acción**: ambos flujos comparten el
   mismo mecanismo backend de "proponer → confirmar", el mismo componente
   de confirmación en la UI, y la misma regla de seguridad (el LLM nunca
   ejecuta una mutación directamente).
4. **Memoria conversacional real** por sesión, para que el relato se
   construya en varios turnos (ej. el usuario menciona sus compromisos en
   un mensaje y pregunta por el concierto en otro).
5. **UI que persiste entre turnos** (superficie estable, actualización
   incremental) en vez de reconstruirse desde cero cada turno.
6. **Dos frontends** consumiendo la misma API: React (`@a2ui/react`, ruta
   crítica de la demo) y Flutter (`genui_a2ui`, cliente secundario).
7. Login con usuarios demo hardcodeados; datos precargados (ingresos,
   gastos fijos, metas, contactos) por usuario demo — el usuario no tiene
   que narrar todo su calendario financiero para que la demo funcione,
   aunque puede mencionar/ajustar cosas por chat.

**Excluido (fuera de alcance para hoy):**

- Streaming/SSE incremental de la UI (un JSON por turno, como en la
  prueba anterior).
- Componentes A2UI custom — se usa el catálogo básico (`basicCatalog` /
  equivalente en `genui`) en ambos lados.
- Registro de usuarios, recuperación de contraseña, refresh tokens,
  multi-tenant real, rate limiting.
- Persistencia de sesión más allá de la vida del proceso backend (todo en
  memoria: conversación, propuestas pendientes).
- Integrar un core bancario open source externo (evaluado: Open Bank
  Project es una plataforma pesada de compliance, no aporta modelado de
  ingresos/gastos recurrentes ni proyección de flujo — más lento de
  adaptar que construir el nuestro).
- Cualquier tercer tipo de consulta financiera (crédito, inversión,
  seguros) — el reto pide un problema resuelto completo, no cobertura
  amplia.

## Riesgo de alcance (explícito)

Dos flujos completos (afford-check+apartado, transferencia+desambiguación)
más dos frontends es más superficie de la que el reto recomienda ("un solo
flujo resuelto completo vale más que cinco pantallas a medias"). Se acepta
este riesgo porque:

- Ambos flujos comparten backend, MCP y contrato de propuesta/confirmación
  — el costo incremental del segundo flujo es bajo una vez construida la
  base.
- React es la ruta crítica de la demo; Flutter es secundario y no bloquea
  la entrega si algo no cierra a tiempo.
- Si el tiempo aprieta, **el flujo de "¿me alcanza?" + apartado es el que
  se garantiza funcionando**; la transferencia con desambiguación y/o
  Flutter se degradan primero.

## Arquitectura

```
┌──────────────────┐   POST /api/login              ┌───────────────────────┐   stdio   ┌──────────────────────────┐
│  React            │ ─────────────────────────────> │   Backend FastAPI      │ ────────> │  MCP server "core         │
│  @a2ui/react       │ <───────────────────────────── │   (auth/authz/         │ <──────── │  bancario" (dueño DB)     │
│                    │   POST /api/chat               │    orquestación,       │           │  SQLite: usuarios,        │
│  Flutter           │   POST /api/confirm-action     │    memoria de sesión)  │           │  cuentas, movimientos,    │
│  genui_a2ui        │                                 │                       │           │  ingresos, gastos fijos,  │
│  (mismo backend)   │                                 │                       │           │  metas, apartados,        │
└──────────────────┘                                 └──────────┬────────────┘           │  contactos                │
                                                                  │ google-genai            └──────────────────────────┘
                                                                  ▼
                                                          Gemini (Google AI Studio)
```

Todo el estado bancario vive en el MCP server (SQLite). El backend nunca
mantiene su propia copia de saldos/movimientos; sí mantiene en memoria de
proceso el historial conversacional por cuenta y las propuestas de acción
pendientes (ambos efímeros, aceptable para una demo).

## Componentes

### 1. MCP server (`mcp_bank/`)

Tablas SQLite:

- `usuarios(account_id PK, username UNIQUE, password_hash, nombre)` —
  passwords con hash (bcrypt), a diferencia de la prueba anterior que los
  guardaba en claro.
- `cuentas(account_id PK/FK, numero_cuenta UNIQUE, saldo REAL, moneda)`.
- `movimientos(id PK, account_id FK, fecha, concepto, monto)`.
- `ingresos_programados(id PK, account_id FK, descripcion, monto,
  frecuencia, proxima_fecha)` — ej. "Nómina", 12,500, quincenal,
  2026-09-12.
- `gastos_fijos(id PK, account_id FK, concepto, monto, frecuencia,
  proxima_fecha)` — ej. "Agua" 320, mensual, 2026-09-13; "Colegiatura hijo
  1" 2400, mensual, 2026-09-15.
- `metas(id PK, account_id FK, descripcion, monto_objetivo, fecha_objetivo,
  monto_ahorrado DEFAULT 0)` — ej. "Concierto X", 1800, 2026-10-13.
- `apartados(id PK, account_id FK, meta_id FK, monto_por_periodo,
  periodicidad, fecha_inicio, estado)`.
- `contactos(id PK, account_id_titular FK, nombre, alias, cuenta_destino,
  relacion)` — seed incluye **al menos dos contactos con el mismo apodo**
  (ej. dos "Pepe") para forzar el caso de desambiguación en la demo.

Tools expuestas por el MCP (todas reciben `account_id` explícito; el MCP
no sabe de JWTs ni sesiones — igual que en la prueba anterior):

**Lectura:**
- `get_saldo(account_id) -> {saldo, moneda}`
- `get_cuenta(account_id) -> {titular, numero_cuenta, saldo}`
- `get_movimientos(account_id, limit=10) -> list[movimiento]`
- `get_ingresos_programados(account_id) -> list[ingreso]`
- `get_gastos_fijos(account_id) -> list[gasto]`
- `get_metas(account_id) -> list[meta]`
- `buscar_contacto(account_id, query) -> list[contacto]` — puede regresar
  0, 1 o varios resultados.
- `simular_flujo_de_caja(account_id, fecha_objetivo, monto_objetivo) ->
  {alcanza: bool, saldo_minimo_proyectado, fecha_critica, margen,
  apartado_sugerido: {monto_por_periodo, periodicidad, num_periodos} |
  null}` — **función Python pura y determinista**: parte del saldo actual,
  aplica en orden cronológico los ingresos y gastos programados entre hoy
  y `fecha_objetivo`, resta `monto_objetivo` en esa fecha, y determina el
  punto más bajo de saldo proyectado. Si en algún momento el saldo
  proyectado sería negativo, calcula cuánto y con qué periodicidad habría
  que apartar desde hoy para evitarlo.

**Mutación (nunca expuestas al LLM; solo las invoca el backend):**
- `ejecutar_transferencia(origen_id, destino_cuenta, monto, concepto) ->
  {ok, movimiento}` — igual que en la prueba anterior (valida saldo
  suficiente; destino inexistente se trata como cuenta externa).
- `crear_apartado(account_id, meta_id, monto_por_periodo, periodicidad) ->
  {ok, apartado}` — descuenta el primer periodo del saldo disponible de
  inmediato (simula el primer apartado) y registra el plan.

### 2. Backend FastAPI

Responsabilidades: autenticación, autorización, orquestación LLM↔MCP,
memoria conversacional, contrato de propuesta/confirmación, validación y
formateo de A2UI.

**Rutas:**

- `POST /api/login {usuario, password} -> {token}` — JWT (`sub=account_id`,
  expiración corta), igual patrón que la prueba anterior.
- `POST /api/chat {mensaje} -> {a2ui_messages: [...]}` (requiere Bearer
  JWT) — ejecuta el loop de orquestación con memoria de conversación.
- `POST /api/confirm-action {proposal_id} -> {a2ui_messages: [...]}`
  (requiere Bearer JWT) — endpoint **único** para confirmar cualquier tipo
  de propuesta (apartado o transferencia); despacha internamente según
  `tipo` de la propuesta.

**Orquestación (`orchestrator.py`):**

1. Lee `account_id` del JWT (nunca del mensaje del usuario ni de lo que
   declare el LLM).
2. Recupera el historial de conversación de esa cuenta (dict en memoria
   del proceso, `HISTORIALES: dict[account_id, list[mensaje]]`, capado a
   las últimas N interacciones) y lo agrega al contexto enviado a Gemini.
3. Declara a Gemini únicamente las tools del allowlist fijo en código:
   `get_saldo`, `get_cuenta`, `get_movimientos`, `get_ingresos_programados`,
   `get_gastos_fijos`, `get_metas`, `buscar_contacto`,
   `simular_flujo_de_caja` (sin `account_id` visible en el schema — se
   inyecta server-side), más dos tools "de solo forma" implementadas
   localmente en el backend (no llaman al MCP):
   - `proponer_apartado(meta_id, monto_por_periodo, periodicidad)`
   - `proponer_transferencia(contacto_id, monto, concepto)` — **requiere
     `contacto_id` numérico, no un nombre libre**, para forzar que el LLM
     haya resuelto la ambigüedad antes de poder proponer.
   Ninguna tool de mutación real (`ejecutar_transferencia`,
   `crear_apartado`) se declara jamás en este contexto.
4. El system prompt instruye:
   - Nunca hacer aritmética financiera él mismo; para cualquier pregunta
     de tipo "¿me alcanza...?" debe llamar `simular_flujo_de_caja`.
   - Si `buscar_contacto` regresa más de un resultado, debe renderizar un
     componente de selección (lista de contactos) y esperar la respuesta
     del usuario antes de llamar `proponer_transferencia`.
   - Toda acción que mueva dinero pasa por `proponer_*`, nunca se afirma
     en texto que "ya se hizo" algo que no se ha confirmado.
   - Responder siempre con un bloque A2UI (nunca texto plano), reusando el
     mismo `surfaceId` de la sesión y prefiriendo `updateComponents`
     incremental sobre recrear toda la superficie.
5. Loop de tool calling (igual patrón que la prueba anterior: máximo N
   rondas, ejecución manual de function calls, reinyección de resultados)
   hasta respuesta final con bloque A2UI.
6. Parsea y valida el bloque contra el catálogo; un reintento con el error
   inyectado si falla; fallback a bloque de error genérico si vuelve a
   fallar.
7. Guarda el turno (mensaje usuario + respuesta) en el historial de la
   cuenta.

**Contrato de propuesta (`proposals.py`):**

```
Propuesta = {
    id: str,
    account_id: str,
    tipo: "apartado" | "transferencia",
    payload: dict,          # datos específicos del tipo
    resumen: str,           # texto para mostrar en la tarjeta de confirmación
    expira_en: datetime,
}
PROPOSALS: dict[str, Propuesta]  # en memoria de proceso, TTL corto (ej. 5 min)
```

`POST /api/confirm-action` valida que la propuesta exista, no haya
expirado y pertenezca al `account_id` del JWT (nunca confía en un
`account_id` que venga del cliente o del LLM); despacha:

- `tipo == "apartado"` → `crear_apartado(account_id, **payload)` en el MCP.
- `tipo == "transferencia"` → **revalida** el contacto (`buscar_contacto`
  por `contacto_id`, confirma que sigue perteneciendo a ese usuario) y
  llama `ejecutar_transferencia(account_id, destino_cuenta, monto,
  concepto)` en el MCP.

Devuelve un nuevo bloque A2UI de confirmación o error.

### 3. Frontends

**React** (`frontend/`, ruta crítica): mismo patrón que la prueba
(`@a2ui/web_core` `MessageProcessor` + `@a2ui/react` `A2uiSurface` +
`basicCatalog`), pero:

- Mantiene un `surfaceId` fijo por sesión y aplica `updateComponents`
  incremental en vez de `resetSurfaces` en cada turno.
- El botón de confirmación de cualquier propuesta muestra explícitamente
  "Verificado por IA" + el resumen de la acción, y pega a
  `POST /api/confirm-action`.

**Flutter** (`frontend_flutter/`, secundario): usa `genui` +
`genui_a2ui` para conectar al mismo backend y catálogo. Implementa el
mismo flujo de login + chat + confirmación. No bloquea la demo si no
llega a tiempo.

## Flujo de datos — ejemplo núcleo ("¿me alcanza para el concierto?")

1. Usuario (en uno o varios turnos): menciona su nómina, sus recibos, o
   simplemente pregunta "¿me alcanza para el concierto del 13 de
   octubre?" — el sistema ya conoce sus ingresos/gastos fijos precargados,
   así que no depende de que el usuario los narre todos.
2. Gemini llama `get_metas` (para resolver a qué "concierto" se refiere si
   no dio el monto) y `simular_flujo_de_caja(fecha_objetivo=2026-10-13,
   monto_objetivo=1800)`.
3. Backend inyecta `account_id`, llama la tool real en el MCP, obtiene el
   resultado determinista (alcanza/no, margen, apartado sugerido).
4. Gemini arma un bloque A2UI: tarjeta de veredicto + (si no alcanza)
   tarjeta con el plan de apartado sugerido y un botón "Activar apartado"
   que dispara `proponer_apartado`.
5. Usuario confirma → `POST /api/confirm-action` → backend valida y llama
   `crear_apartado` real en el MCP → responde con bloque de confirmación.

## Flujo de datos — ejemplo transferencia con desambiguación

1. Usuario: "deposítale 500 a mi hermano Pepe".
2. Gemini llama `buscar_contacto(query="Pepe")` → regresa 2 resultados.
3. Backend regresa los resultados como function response; el prompt obliga
   a Gemini a responder con un bloque A2UI de selección (lista de los 2
   contactos) en vez de proponer la transferencia.
4. Usuario elige uno (la selección se manda como un nuevo mensaje al
   `/api/chat`, ej. "el segundo, mi hermano de Monterrey").
5. Gemini llama `proponer_transferencia(contacto_id=<resuelto>, monto=500,
   concepto=...)` → tarjeta de confirmación con el contacto ya verificado.
6. Usuario confirma → `POST /api/confirm-action` → backend revalida el
   contacto y ejecuta `ejecutar_transferencia` real.

## Autorización — reglas duras (heredadas y extendidas de la prueba)

- El LLM nunca ve ni puede expresar `account_id`/`origen_id` en ningún
  tool schema — se inyecta siempre server-side desde el JWT.
- Ninguna tool que muta datos (`ejecutar_transferencia`, `crear_apartado`)
  se declara jamás en el contexto del LLM; solo las invoca el backend
  desde `/api/confirm-action`, tras validar la propuesta contra el JWT.
- `proponer_transferencia` exige `contacto_id` resuelto, no un nombre
  libre — el LLM no puede saltarse la desambiguación aunque quisiera.
- El allowlist de tools visibles al LLM se define explícitamente en
  código, no se deriva de `list_tools()` del MCP.

## Manejo de errores

- MCP no responde / tool lanza excepción → backend captura, responde con
  bloque A2UI de error, nunca propaga la excepción cruda.
- Bloque A2UI del LLM no valida contra el catálogo → un reintento con el
  error inyectado; si vuelve a fallar, fallback a bloque de error
  genérico.
- JWT ausente/inválido/expirado → 401; el frontend limpia sesión y vuelve
  a login.
- Propuesta expirada, no encontrada, o de un `account_id` distinto en
  `/api/confirm-action` → 409 con bloque A2UI explicando que hay que pedir
  la acción de nuevo.
- `buscar_contacto` sin resultados → el LLM debe decir explícitamente que
  no encontró al contacto y pedir más datos, nunca inventar uno.
- `simular_flujo_de_caja` con `fecha_objetivo` en el pasado o inválida →
  la tool regresa un error estructurado; el LLM debe pedir una fecha
  válida.

## Testing

- **MCP server**: tests unitarios de cada tool contra una DB SQLite de
  prueba con seed conocida — incluyendo varios casos de
  `simular_flujo_de_caja` (alcanza justo, no alcanza, alcanza con margen
  amplio, fecha objetivo antes del próximo ingreso) y de `buscar_contacto`
  (0, 1 y N resultados).
- **Backend**: tests de auth (igual que la prueba); tests del orquestador
  verificando que `account_id` siempre es el del JWT, que las tools de
  mutación nunca son alcanzables desde `/api/chat`, y que
  `proponer_transferencia` sin `contacto_id` resuelto no es aceptado;
  tests de `/api/confirm-action` para ambos tipos de propuesta (éxito,
  expirada, de otra cuenta).
- **Frontend**: prueba manual en navegador de ambos flujos completos
  (afford-check + apartado, transferencia + desambiguación). No se
  justifica una suite automatizada de UI para una demo de un día.
- **Flutter**: prueba manual del mismo flujo básico (login + una consulta
  + una confirmación), sin exigir paridad total con React.

## Configuración

`.env` en la raíz del backend (en `.gitignore`):

```
GOOGLE_AI_STUDIO_API_KEY=...
GEMINI_MODEL=...
JWT_SECRET=...
BANK_DB_PATH=banco.db
```

Frontend React: `VITE_API_BASE_URL=http://localhost:8000`.

## Dependencias (informadas por la prueba anterior, ya verificadas)

- Backend: `fastapi`, `uvicorn`, `google-genai`, `a2ui-agent-sdk`
  (`a2ui.inference_formats.direct_json`), `mcp`, `pyjwt`, `bcrypt`,
  `python-dotenv`. Tests: `pytest`, `pytest-asyncio`.
- Frontend React: Vite + React + TypeScript, `@a2ui/react`,
  `@a2ui/web_core`.
- Frontend Flutter: `genui`, `genui_a2ui` (paquetes oficiales de Google en
  pub.dev).

## Fuera de este spec (posible follow-up, no hoy)

- Streaming SSE con parser incremental de A2UI.
- Componentes A2UI custom para banca (ej. tarjeta de flujo de caja con
  gráfica propia en vez de `List`/`Card` genéricos).
- Persistencia real de sesión/propuestas (hoy en memoria de proceso).
- Registro de usuarios y recuperación de contraseña.
- Cobertura de otros dominios del reto (crédito, inversión, seguros).
