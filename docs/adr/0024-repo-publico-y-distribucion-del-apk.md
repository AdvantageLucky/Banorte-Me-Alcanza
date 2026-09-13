# ADR 0024 — Repo público y distribución del APK por Release + landing page

**Estado:** Aceptada · 2026-09-13

## Contexto

Queríamos una forma de que cualquiera en el hackathon (jurado, otros
equipos) llegara a la app sin depender de que nosotros tuviéramos el
celular a la mano: una landing page con dos QR — uno a la app web, otro a
la descarga directa del APK de Android — y un workflow de CI que
mantuviera el APK actualizado en cada push.

El repo (`AdvantageLucky/Banorte-Me-Alcanza`) era privado. Dos cosas se
rompen con eso:

- GitHub Pages en un repo privado exige un plan de pago (Pro/Team/Enterprise);
  la API lo confirma explícitamente (`Your current plan does not support
  GitHub Pages for this repository`).
- Los *assets* de un Release en un repo privado exigen sesión de GitHub
  para descargarse — alguien escaneando el QR desde su celular vería un
  login, no el APK.

## Decisión

- **El repo se hace público.** Es la única opción que deja tanto Pages
  como el Release realmente accesibles sin cuenta, sin depender de
  infraestructura propia (homelab) para servir la landing.
- **`.github/workflows/release-apk.yml`** compila el APK de Flutter en cada
  push a `main` que toque `flutter_app/` (firmado con la clave de debug de
  Flutter — suficiente para instalar manualmente, nunca para Play Store) y
  lo sube como asset de un Release fijo con tag `latest-apk`: el mismo tag
  se actualiza en cada corrida, así que el link/QR de descarga nunca
  cambia.
- El mismo workflow despliega `docs/landing/` (una página estática, sin
  build) a GitHub Pages. Los dos QR (`qr-web.png` hacia
  `frontend.jzackarias.lat`, `qr-apk.png` hacia el asset del Release) están
  pre-generados y viven en el repo — no se regeneran en CI porque las URLs
  que codifican son estables.

## Consecuencias

- El código fuente completo queda visible para los demás equipos del
  hackathon mientras dure la competencia — aceptado a cambio de que la
  distribución funcione de verdad para gente externa.
- El APK usa la firma de debug de Flutter: sirve para instalar a mano
  (Android pide permitir "orígenes desconocidos"), no es publicable en
  Play Store tal cual.
- Apunta siempre a `https://homelab.tail8dc7f1.ts.net` como backend — si
  el homelab está caído, el APK instalado no funciona aunque la descarga
  sí.
- Activar Pages por primera vez en un repo recién hecho público es un paso
  manual de una sola vez (`gh api .../pages -X POST -f build_type=workflow`
  o desde Settings → Pages); documentado en `docs/landing/README.md`.
