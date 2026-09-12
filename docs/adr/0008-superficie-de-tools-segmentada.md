# ADR 0008 — Tres niveles de visibilidad para las tools MCP

**Estado:** Aceptada · 2026-09-11

## Contexto

El servidor MCP expone 35 tools. Si el LLM las viera todas, podría ejecutar una
transferencia porque "el usuario lo pidió", leer el detalle crudo de movimientos
de otra cuenta, o borrar una meta. El reto exige un flujo accionable, pero un
banco no puede dejar que el modelo mute estado por su cuenta.

## Decisión

Las tools se clasifican en el orquestador, no en el servidor:

| Nivel | Quién las llama | Ejemplos |
|---|---|---|
| Lectura | Gemini, vía function calling (`_READ_ONLY_TOOLS`) | `get_saldo`, `simular_flujo_de_caja`, `get_resumen_movimientos` |
| Mutación | Solo `confirm_action`, tras confirmación humana | `ejecutar_transferencia`, `crear_apartado`, `crear_meta` |
| Interna | Solo rutas REST y el orquestador | `get_contacto`, CRUD `actualizar_*`/`eliminar_*`, conversaciones, sugerencias, score |

El LLM además recibe agregados (`get_resumen_movimientos`) y no el detalle
(`get_movimientos`).

## Consecuencias

- El modelo no tiene forma de mutar nada: solo puede *proponer*
  ([ADR 0009](0009-patron-proponer-confirmar.md)).
- Añadir una tool al servidor no la expone al modelo; hay que agregarla
  explícitamente a `_READ_ONLY_TOOLS` y a `read_only_tool_declarations()`.
- Editar/borrar por chat no existe a propósito: el prompt le dice al modelo que
  lo mande a la pestaña correspondiente.
