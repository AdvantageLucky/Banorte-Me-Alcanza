# Landing page de descarga

Página estática con identidad de marketing propia (`index.html` +
`banorberto.png`, la mascota, tomada de
`frontend/src/assets/images/banorberto.png` + `qr-web.png` + `qr-apk.png`)
que [`.github/workflows/release-apk.yml`](../../.github/workflows/release-apk.yml)
publica en GitHub Pages en cada push a `main` que toque `flutter_app/` o
esta carpeta. El mismo workflow compila el APK y lo sube como asset del
Release fijo `latest-apk`, así que el link/QR de descarga siempre apunta al
build más reciente sin cambiar de URL.

**Ya está en línea:** el repo es público, Pages está activado
(`build_type: workflow`) y `https://advantagelucky.github.io/Banorte-Me-Alcanza/`
responde 200. `qr-landing.png` es el QR de ESA página completa (no de
`qr-web.png`/`qr-apk.png` por separado) — es el que va en diapositivas o
cualquier lugar donde solo quepa un QR: quien lo escanea llega a la landing
y ahí elige web o APK con contexto, en vez de dos códigos sueltos sin
explicación.

## Regenerar los QR si cambian las URLs

```bash
uvx --from qrcode[pil] qr --output docs/landing/qr-web.png --error-correction=M \
  "https://frontend.jzackarias.lat"
uvx --from qrcode[pil] qr --output docs/landing/qr-apk.png --error-correction=M \
  "https://github.com/AdvantageLucky/Banorte-Me-Alcanza/releases/download/latest-apk/me-alcanza.apk"
uvx --from qrcode[pil] qr --output docs/landing/qr-landing.png --error-correction=H \
  "https://advantagelucky.github.io/Banorte-Me-Alcanza/"
```
