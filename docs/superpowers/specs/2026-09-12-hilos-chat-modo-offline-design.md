# Diseño: Hilos de chat con memoria + modo offline determinista + caso sin proveedor

## Objetivo

Hoy `Orchestrator.handle_message` es **completamente sin memoria**: cada
request HTTP a `/api/chat` arma `contents = [mensaje]` desde cero, sin
historial. Este spec agrega (1) hilos de conversación persistentes con
memoria real entre turnos (estilo ChatGPT/Claude — varias conversaciones,
cada una con su propio contexto), (2) un modo offline determinista para
cuando Gemini no responde (cuota agotada, sin API key, error de red), y (3)
el caso explícito de "no hay proveedor configurado".

Es el sub-proyecto más grande de los 4 — depende de nada de los otros 3,
pero es el que más superficie nueva toca (schema, orquestador, rutas).

## Verificación previa contra la librería real (ya hecha en esta sesión)

Antes de diseñar el multi-turno se verificó contra el `google-genai`
instalado (no se asumió): `types.Content` es un modelo con exactamente los
campos `role` y `parts`; se construye así:

```python
types.Content(role="user", parts=[types.Part.from_text(text="hola")])
```

El código ya existente en `_run_tool_loop` ya mezcla, dentro de una sola
llamada, un `contents` que empieza como texto plano y le va agregando
objetos `types.Content` reales conforme corre el tool-loop (esto ya
funciona hoy, es el código actual) — confirma que pasar una lista de
`types.Content` explícitos como semilla inicial (en vez de `[mensaje]`) es
compatible con el mismo mecanismo, sin sorpresas de la librería.

## Parte 1 — Hilos de chat con memoria

### Modelo de datos

```sql
CREATE TABLE IF NOT EXISTS conversaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES usuarios(account_id),
    titulo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensajes_conversacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversacion_id INTEGER NOT NULL REFERENCES conversaciones(id),
    rol TEXT NOT NULL,          -- 'user' | 'model'
    contenido TEXT NOT NULL,    -- texto crudo tal cual se mandó/generó (incluye el bloque <a2ui-json> completo para 'model')
    created_at TEXT NOT NULL
);
```

`titulo` se autogenera del primer mensaje del usuario (primeros 60
caracteres) — sin LLM adicional, sin campo editable por ahora.

### `handle_message` gana memoria

Firma nueva: `handle_message(account_id, conversacion_id, mensaje)`. Antes
de correr el tool-loop, se cargan los mensajes previos de esa conversación
y se arma `contents` como una lista de `types.Content(role=rol,
parts=[types.Part.from_text(text=contenido)])` por cada mensaje histórico,
más el mensaje nuevo del usuario en el mismo formato. Al terminar (éxito o
error), se persisten dos filas nuevas en `mensajes_conversacion`: el
mensaje del usuario, y el texto final generado por el modelo (el mismo
`final_text` que hoy ya se parsea a bloques A2UI — se guarda tal cual, con
el `<a2ui-json>` incluido, para poder re-alimentarlo íntegro en el próximo
turno).

**Compatibilidad hacia atrás**: `conversacion_id` es **opcional** en
`ChatRequest`. Si no se manda, el backend crea una conversación nueva de un
solo turno automáticamente (mismo comportamiento de hoy, sin romper ningún
cliente existente). Los clientes que quieran hilos reales empiezan a
mandarlo explícitamente.

### Endpoints REST nuevos

```
GET    /api/conversaciones                  -- listar hilos de la cuenta (id, titulo, created_at, updated_at)
POST   /api/conversaciones                  -- crear uno nuevo, titulo opcional
GET    /api/conversaciones/{id}/mensajes    -- historial completo (rol, contenido, created_at)
DELETE /api/conversaciones/{id}
```

`POST /api/chat` se modifica: `ChatRequest` gana `conversacion_id:
int | None = None`.

## Parte 2 — Modo offline determinista

Variable de entorno `LLM_PROVIDER` (`gemini` default, o `fake`). En modo
`fake`, el `Orchestrator` nunca llama a `google-genai` — usa un módulo
nuevo `fake_provider.py` con una función pura
`generar_respuesta_offline(mensaje: str) -> str` que devuelve texto con el
mismo formato `<a2ui-json>...</a2ui-json>` que produce Gemini, elegido por
palabras clave simples del mensaje (saldo, meta/ahorro, o un genérico
"no puedo procesar esto en modo offline"). Sirve para ensayar la demo sin
gastar cuota, y como **fallback automático**: si la llamada real a Gemini
lanza cualquier excepción (incluyendo 429/cuota agotada), el orquestador
intenta el fallback offline antes de caer al bloque de error genérico,
mostrando una tarjeta que dice explícitamente "modo offline temporal" (no
finge ser una respuesta real).

## Parte 3 — Caso sin proveedor configurado

Si `GOOGLE_AI_STUDIO_API_KEY` no está seteada al arrancar el backend (y
`LLM_PROVIDER` no es `fake` explícitamente), el backend arranca igual pero
force `LLM_PROVIDER=fake` automáticamente con un log de advertencia — nunca
debe fallar el arranque completo del servidor por falta de API key.

## Fuera de alcance

Cualquier UI de hilos en Flutter/React (lista de conversaciones, cambiar
entre ellas) — este spec es 100% backend. Edición del título de una
conversación. Streaming de la respuesta del modelo turno a turno.

## Testing

Tests de `db.py` (CRUD de conversaciones/mensajes), tests de
`orchestrator.py` (multi-turno reconstruye `contents` correctamente,
persiste ambos mensajes, fallback a modo offline cuando `generate_content`
lanza una excepción), tests de `fake_provider.py` (respuestas por keyword),
tests de `routes.py` (endpoints de conversaciones, `/api/chat` sin
`conversacion_id` sigue funcionando).

## Nota para quien ejecute este plan

Es el sub-proyecto más grande de los 4 y el único con incertidumbre técnica
real (el comportamiento exacto de `google-genai` con historial multi-rol
largo no se probó contra la API real en esta sesión, solo se verificó la
construcción de objetos `Content` — probar contra Gemini real con al menos
3-4 turnos antes de dar esto por terminado). El diseño del modo offline es
deliberadamente simple (keywords, no NLP) — es una red de seguridad para
demo, no un modelo real.
