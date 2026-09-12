# ADR 0021 — Pruebas: MCP real por stdio, LLM mockeado, TDD por feature

**Estado:** Aceptada · 2026-09-11

## Contexto

Con cuatro personas tocando el mismo backend en paralelo durante 48 horas, la
suite es lo único que evita que un merge rompa el flujo de la demo sin que nadie
lo note. Pero probar contra Gemini real es lento, cuesta cuota y no es
determinista.

## Decisión

- El servidor MCP se levanta **de verdad** en los tests (`stdio_client` contra
  una DB temporal); `test_server.py` fija el conjunto exacto de tools expuestas
  para que una tool nueva o borrada falle un test.
- Gemini se mockea en los tests del orquestador; el modo offline
  ([ADR 0016](0016-modo-offline-determinista.md)) se prueba como función pura.
- Los motores deterministas se prueban con fixtures sintéticos por regla.
- Cada feature se construyó en rojo → verde → commit, con commits
  convencionales (`feat:`, `fix:`, `docs:`).
- El frontend prueba con vitest los módulos JS puros (cliente API, storage,
  filtros de mensajes); los componentes React se verifican manualmente.

## Consecuencias

- 227 tests en Python y 50 en el frontend corren sin red en ~3 minutos.
- El contrato MCP está cubierto; el contrato con Gemini (formato exacto del
  `<a2ui-json>`) solo se valida en vivo. Antes de la demo hay que correr los dos
  flujos contra el modelo real.
- Los tests de integración dependen de las cifras del seed
  ([ADR 0013](0013-sqlite-con-seed-relativo-a-hoy.md)).
