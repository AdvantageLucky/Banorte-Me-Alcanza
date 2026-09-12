# ADR 0018 — Backend público por Tailscale Funnel; frontend por Cloudflare con dominio propio

**Estado:** Aceptada · 2026-09-12

## Contexto

El homelab ([ADR 0017](0017-self-hosting-en-homelab-con-docker-compose.md))
está detrás de NAT sin IP pública. Hacen falta dos URLs HTTPS válidas: una para
el navegador del jurado (frontend) y otra que ese navegador pueda llamar desde
cualquier red (backend). Abrir puertos en el router y gestionar certificados a
mano no era una opción en el tiempo disponible.

## Decisión

- **Backend:** publicado con *Tailscale Funnel* en
  `https://homelab.tail8dc7f1.ts.net/`. Tailscale termina TLS con un certificado
  válido y reenvía a uvicorn; no hay proxy inverso propio delante del backend.
- **Frontend:** el contenedor nginx se publica detrás de **Cloudflare** con un
  dominio del equipo, `https://frontend.jzackarias.lat/`. Cloudflare termina
  TLS y cachea los assets versionados; `index.html` va con `no-cache` desde
  nginx.
- El bundle del frontend se construye con
  `VITE_API_BASE_URL=https://homelab.tail8dc7f1.ts.net`; el backend responde
  CORS reflejando ese origen.

## Consecuencias

- HTTPS válido en ambos sin tocar el router ni gestionar certificados.
- Dos proveedores distintos para dos piezas: si Tailscale cae, el frontend
  sigue arriba pero sin backend; y viceversa.
- La URL del backend queda pública y fija en el bundle: cambiarla implica
  reconstruir la imagen del frontend.
- **El backend está expuesto tal cual:** `/docs` (Swagger) es público,
  `allow_origins` en código es `*` y no hay rate limiting delante de uvicorn.
  Aceptable para una demo con datos sintéticos; sería la primera cosa a cerrar
  en cualquier otro contexto.
- El nombre `*.ts.net` delata la infraestructura; a cambio se obtuvo en minutos.
