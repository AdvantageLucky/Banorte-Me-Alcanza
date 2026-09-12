# ADR 0017 — Self-hosting en un homelab con Docker Compose

**Estado:** Aceptada · 2026-09-12

## Contexto

Había que publicar backend y frontend para la demo y para que el jurado los
abra desde cualquier dispositivo. Las opciones evaluadas: PaaS gratuito
(Render, Railway, Fly), nube con crédito, o un homelab de un integrante que ya
está encendido y tiene Docker.

Los PaaS gratuitos duermen el contenedor tras minutos de inactividad (un
arranque en frío justo cuando el juez pregunta), imponen límites de CPU/RAM
que el subproceso MCP + SQLite tocan, y sus URLs públicas son efímeras o
genéricas. La nube con crédito exige tarjeta y configuración que no aporta al
reto.

## Decisión

Desplegar con `docker compose` en un homelab propio: servicio `backend` (imagen
con backend + MCP, puerto 10000, SQLite en volumen `banco-db`) y servicio
`frontend` (build multi-stage Node → nginx, puerto 8080, con
`VITE_API_BASE_URL` horneado en build). `restart: unless-stopped` en ambos.

## Consecuencias

- Sin arranque en frío, sin límites de cuota, sin tarjeta; una máquina que ya
  se controla.
- La exposición pública es un problema aparte
  ([ADR 0018](0018-exposicion-publica-tailscale-funnel-y-cloudflare.md)): el
  homelab no tiene IP pública ni puertos abiertos.
- Un solo punto de falla físico: si esa máquina o su red caen durante la
  presentación no hay réplica. Mitigación: correr también en local con el mismo
  `docker compose` y cambiar la URL del frontend si hace falta.
- El operador del homelab es una persona; el conocimiento de despliegue debe
  quedar en este ADR y en el README, no en su cabeza.
