# ADR 0012 — Dos clientes (React y Flutter) sobre el mismo stream A2UI

**Estado:** Aceptada · 2026-09-12

## Contexto

Un solo frontend habría bastado para el reto. Pero el argumento central de A2UI
es que "la interfaz viaja": el agente describe, cualquier cliente renderiza. Si
solo hay un cliente, esa afirmación no se puede demostrar; podría ser un
frontend acoplado a su backend que casualmente manda JSON.

## Decisión

Dos clientes que consumen exactamente el mismo `POST /api/chat` y el mismo
`POST /api/confirm-action`: React con `@a2ui/react` + `@a2ui/web_core`, y
Flutter con `a2ui_core` + `genui`. Ninguno tiene lógica de negocio; ambos
enrutan el evento `confirmar_accion` al mismo endpoint. El backend no sabe cuál
lo está llamando.

## Consecuencias

- Es la prueba tangible de que el contrato A2UI es real y de que el equipo no
  está casado con un framework.
- Duplica el costo de cada componente nuevo y de cada verificación manual.
- Si Flutter no se muestra en la demo, el jurado no se entera y la inversión
  no cuenta.

*Actualización 2026-09-13:* Flutter dejó de ser "solo el chat". Tiene
Sugerencias (tarjetas A2UI del backend con Atender/Descartar), Asistente con
memoria de hilo y Yo con CRUD completo; la propuesta generada por el LLM bajo
cada sugerencia sigue pendiente. Ver `flutter_app/README.md`.
