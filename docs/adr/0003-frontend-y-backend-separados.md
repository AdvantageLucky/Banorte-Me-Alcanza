# ADR 0003 — Frontend y backend como despliegues separados

**Estado:** Aceptada · 2026-09-11

## Contexto

Una app monolítica (backend sirviendo su propio HTML) habría sido más simple de
desplegar. Pero el reto pide que la interfaz *viaje* — el agente describe la UI
en A2UI y un cliente la renderiza — y queríamos demostrar que ese contrato es
real y no una abstracción decorativa.

## Decisión

El backend expone solo JSON (REST + bloques A2UI) bajo `/api`; no sirve ningún
HTML. Los clientes son artefactos independientes: una SPA React/Vite compilada a
estáticos y servida por nginx, y una app Flutter. Cada uno se construye, se
despliega y se versiona por separado. El único acoplamiento es la URL base del
backend, que el frontend recibe en build (`VITE_API_BASE_URL`).

## Consecuencias

- Fue posible tener dos clientes sobre el mismo backend sin tocarlo
  ([ADR 0012](0012-dos-clientes-mismo-stream-a2ui.md)).
- Hay que resolver CORS (el backend lo hace por origen) y desplegar dos cosas en
  vez de una ([ADR 0018](0018-exposicion-publica-tailscale-funnel-y-cloudflare.md)).
- La URL del backend queda horneada en el bundle: cambiarla exige reconstruir la
  imagen del frontend.
