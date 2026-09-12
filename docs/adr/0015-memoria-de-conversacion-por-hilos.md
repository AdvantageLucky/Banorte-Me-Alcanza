# ADR 0015 — Memoria de conversación por hilos, con ventana acotada

**Estado:** Aceptada · 2026-09-12

## Contexto

La primera versión de `handle_message` armaba `contents = [mensaje]` en cada
request: sin memoria, el modelo no podía resolver "y si fueran 500 en vez de
800". El reto pide que "la interacción regrese al agente como contexto". El
prompt incluso tuvo que explicar al modelo que "la conversación no conserva
memoria" para forzar la desambiguación en un solo turno.

## Decisión

Tablas `conversaciones` y `mensajes_conversacion` en el core bancario, con CRUD
expuesto como tools MCP internas. `POST /api/chat` acepta `conversacion_id`
opcional; sin él se crea un hilo nuevo. El orquestador carga los últimos
`_MAX_HISTORIAL_MENSAJES = 10` mensajes como `types.Content` y persiste el
mensaje del usuario y el texto final del modelo (con el bloque `<a2ui-json>`
íntegro). Rutas REST para listar, crear, leer y borrar hilos.

## Consecuencias

- El modelo ve el contexto previo y puede refinar propuestas.
- La ventana de 10 acota costo y evita crecimiento indefinido del contexto.
- Las respuestas del modo offline ([ADR 0016](0016-modo-offline-determinista.md))
  nunca se persisten: no contaminan el historial con boilerplate.
- **Deuda:** `confirm_action` sigue fuera del hilo — ejecuta y devuelve una
  tarjeta fija sin pasar por el modelo. El ciclo "la acción vuelve al agente"
  está cerrado para mensajes, no para confirmaciones.
