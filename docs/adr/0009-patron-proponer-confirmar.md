# ADR 0009 — Toda mutación pasa por proponer → confirmar

**Estado:** Aceptada · 2026-09-11

## Contexto

El flujo accionable del reto implica que una interacción con la UI generada
produzca un cambio real. Dejar que el LLM llame `ejecutar_transferencia` cuando
cree que el usuario quiere es inaceptable en banca: el modelo alucina, el
usuario puede haberse expresado mal, y una respuesta HTTP reintentada
ejecutaría dos veces.

## Decisión

El LLM solo tiene acceso a funciones `proponer_*` del backend (no son tools MCP).
Cada una valida lo necesario leyendo del MCP y crea una `Proposal` en memoria
con `id`, `account_id`, `tipo`, `payload` y `created_at`
([`proposals.py`](../../src/me_alcanza/backend/proposals.py)). El modelo pinta
una tarjeta con un `Button` cuya acción es `confirmar_accion` con ese
`proposalId`. Solo `POST /api/confirm-action` ejecuta: verifica dueño y TTL
(5 min), **descarta la propuesta antes** de llamar al MCP, y luego muta.

## Consecuencias

- El modelo nunca afirma que algo se ejecutó; el prompt lo prohíbe y el código lo
  hace imposible.
- Dos confirmaciones concurrentes de la misma propuesta ejecutan una sola vez.
- La desambiguación de contactos sale gratis: ante dos "Pepe", el modelo crea
  dos propuestas y dos tarjetas en el mismo turno; el usuario elige tocando.
- Las propuestas viven en memoria del proceso: un reinicio las pierde y un
  segundo worker no las vería. Aceptado para la demo (un solo proceso).
- Hoy `confirm_action` devuelve una tarjeta fija y no vuelve al LLM; cerrar ese
  ciclo es deuda registrada en [ADR 0015](0015-memoria-de-conversacion-por-hilos.md).
