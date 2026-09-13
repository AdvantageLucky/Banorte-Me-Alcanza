# Landing page de descarga

Página estática con identidad de marketing propia (`index.html` +
`banorberto.png`, la mascota, tomada de
`frontend/src/assets/images/banorberto.png` + `qr-web.png` + `qr-apk.png`)
que [`.github/workflows/release-apk.yml`](../../.github/workflows/release-apk.yml)
publica en GitHub Pages en cada push a `main` que toque `flutter_app/` o
esta carpeta. El mismo workflow compila el APK y lo sube como asset del
Release fijo `latest-apk`, así que el link/QR de descarga siempre apunta al
build más reciente sin cambiar de URL.

## Requisito: el repo debe ser público

- **GitHub Pages** en un repo privado necesita un plan de pago (Pro/Team/Enterprise).
- Aunque Pages funcionara, los **assets de un Release en un repo privado**
  exigen sesión de GitHub para descargarse — alguien escaneando el QR desde
  su celular vería un login, no el APK.

Con el repo público, ambos son gratis y de verdad públicos.

## Activar Pages (una sola vez, después de hacer público el repo)

```bash
gh api repos/AdvantageLucky/Banorte-Me-Alcanza/pages -X POST -f build_type=workflow
```

o desde la UI: **Settings → Pages → Build and deployment → Source: GitHub
Actions**. Después de eso, el workflow la despliega solo en cada push.

La URL final es `https://advantagelucky.github.io/Banorte-Me-Alcanza/`.

## Regenerar los QR si cambian las URLs

```bash
uvx --from qrcode[pil] qr --output docs/landing/qr-web.png --error-correction=M \
  "https://frontend.jzackarias.lat"
uvx --from qrcode[pil] qr --output docs/landing/qr-apk.png --error-correction=M \
  "https://github.com/AdvantageLucky/Banorte-Me-Alcanza/releases/download/latest-apk/me-alcanza.apk"
```
