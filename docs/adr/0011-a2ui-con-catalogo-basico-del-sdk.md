# ADR 0011 — A2UI v0.9 con el catálogo básico del SDK

**Estado:** Aceptada con deuda reconocida · 2026-09-11

## Contexto

A2UI (o equivalente) es obligatorio. El SDK oficial trae un *catálogo básico*
(`Card`, `Column`, `Row`, `Text`, `Button`, `List`, `Divider`, `Modal`,
`TextField`, …) con generador de prompt, schema y renderers para React y
Flutter. El reto, sin embargo, dice que "el sistema de componentes que el agente
invoca lo diseña y programa el equipo".

## Decisión

Arrancar con el catálogo básico del SDK restringido a 8 componentes
(`_ALLOWED_COMPONENTS`) para que el ciclo completo — prompt, tool-loop,
validación, render en dos clientes, confirmación — funcionara el primer día. La
identidad visual se aplica encima: paleta Banorte en las variables del tema,
parche a `@a2ui/react` para restaurar clases CSS y hoja de estilos del catálogo
cargada explícitamente. Los componentes de dominio propios (línea de tiempo del
flujo de caja, selector de plan de apartado) se registran como extensión del
catálogo cuando el ciclo ya esté cerrado.

## Consecuencias

- El ciclo funciona de punta a punta en React y Flutter con el mismo JSON.
- Las tarjetas son genéricas: el jurado puede percibirlas como "biblioteca de
  UI entregada" aunque el renderer y los estilos sean nuestros. Es la deuda más
  visible del proyecto y afecta el 20 % de "calidad y adaptabilidad de la UI".
- Cualquier componente propio debe existir en ambos renderers o romper
  [ADR 0012](0012-dos-clientes-mismo-stream-a2ui.md).
