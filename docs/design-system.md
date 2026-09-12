# Sistema de diseño — me-alcanza (Banorte)

Paleta y tipografía estandarizadas para todo el proyecto (React hoy,
Flutter si se construye). El objetivo es que cualquier pantalla nueva —
incluyendo las tarjetas que arma el LLM vía A2UI — se vea consistente y
reconocible como Banorte, sin que cada quien improvise colores.

## Origen de los colores

Banorte no publica un manual de marca descargable con los hex exactos.
Los valores de abajo vienen de rastreadores de marca de terceros.
Brandfetch (brandfetch.com/banorte.com) agrega en realidad **dos
paletas distintas** que conviene no mezclar sin criterio — la del
logotipo y la del sitio web — corroboradas cada una por dos fuentes
independientes que coinciden entre sí:

- **Paleta del logotipo**: [Banorte Logo Colors — Hex, RGB and CMYK Color Codes](https://brandpalettes.com/banorte-logo-colors/)
- **Paleta del sitio web** (la que se usa en este proyecto): [Banorte Website Colors](https://brandpalettes.com/banorte-website-colors/), [Banorte Website Color Scheme](https://www.schemecolor.com/banorte-website-color-scheme.php)

(Brandfetch mismo bloqueó el acceso directo por falta de API key; los
valores de abajo se verificaron cruzando estas otras dos fuentes en
vez de confiar en una sola.)

Si el equipo tiene acceso a un manual de marca oficial de Banorte (por
ejemplo, entregado por los organizadores del hackathon), esos valores
tienen prioridad sobre los de abajo — actualiza esta tabla y el CSS
citando la fuente nueva.

### Paleta del logotipo (referencia, no usada como base del UI)

| Token | Hex | Nota |
|---|---|---|
| Rojo del logo (Imperial/Crayola Red) | `#EF2945` | Un rojo ligeramente más rosado/claro que el rojo del sitio web. Úsalo solo si necesitas reproducir el logotipo exacto (ej. un asset de marca), no como color de UI. |
| Café corporativo | `#684D3D` | Color secundario del logo, casi no aparece en el sitio web real. Disponible como acento terroso opcional si el equipo quiere diferenciarse del clásico rojo-gris, pero no es necesario para cumplir con la marca. |

### Paleta del sitio web (la que usa este proyecto)

Esta es la que se usa en la app — es la que Banorte realmente aplica en
sus productos digitales, más relevante para una app financiera que la
paleta del logotipo impreso.

### Colores adicionales (Brandfetch, extraídos de imágenes del sitio)

Brandfetch (perfil marcado como **"Unclaimed brand"** — es decir,
extraído automáticamente, no verificado ni enviado por Banorte) lista
además estos tres colores, probablemente sacados de banners
promocionales del sitio (créditos, tasas, campañas) y no del sistema de
UI central:

| Hex | Nombre (Brandfetch) | Nota |
|---|---|---|
| `#EB0029` | Torch Red | Prácticamente idéntico al rojo de marca ya documentado (`#EC0029`) — confirma el rojo como color primario, no aporta uno nuevo. |
| `#F8D44C` | Energy Yellow | No aparece en las otras fuentes. Útil como acento terciario (ej. resaltar una tasa, un dato destacado, un estado de "atención" distinto del rojo de error) — no reemplaza al gris/blanco como base. |
| `#108DCD` | Cerulean | Tampoco aparece en otras fuentes. Útil como color informativo/secundario si se necesita distinguir categorías en una gráfica o un estado "neutral" que no sea ni éxito ni error ni advertencia. |

Como el perfil está sin reclamar, ninguno de estos tres valores es
oficial — trátalos como candidatos a acento, no como parte obligatoria
de la identidad. Si se usan, que sea con moderación (ej. un badge, un
ícono, una barra de una gráfica), nunca como color de fondo o de texto
principal.

## Paleta de color

| Token | Hex | Uso |
|---|---|---|
| **Rojo Banorte** (primario) | `#EC0029` | Marca, botones primarios, encabezados, acentos. Nunca como color de texto de párrafo sobre blanco (ver nota de contraste abajo). |
| **Gris intenso** (texto) | `#6A6867` | Texto secundario, bordes de énfasis, iconografía neutra. |
| **Gris plata** (bordes/superficies) | `#C7C9C9` | Bordes, separadores, estados deshabilitados. |
| **Blanco técnico** (fondo) | `#F5F5F5` | Fondo general de la app (no blanco puro — le da textura sin perder legibilidad). |
| Superficie | `#FFFFFF` | Tarjetas, inputs, modales — blanco puro para que resalten sobre el fondo técnico. |
| Texto principal | `#1F1F1F` | Texto de cuerpo sobre fondo claro (no usar gris marca ni rojo para párrafos largos). |
| Éxito | `#1E8E3E` | Confirmaciones (transferencia/apartado exitoso). No es parte de la marca Banorte; es un verde semántico estándar, elegido por convención universal de "acción completada". |
| Error | `#C5221F` | Mensajes de error, saldo insuficiente. Deliberadamente distinto del rojo de marca para que un error nunca se confunda visualmente con un botón o acento de marca. |
| Acento amarillo (opcional) | `#F8D44C` | Solo como resalte puntual (badge, dato destacado). No es color base — ver "Colores adicionales" abajo. |
| Acento azul (opcional) | `#108DCD` | Solo como color informativo/categórico puntual (ej. gráficas). No es color base — ver "Colores adicionales" abajo. |

### Nota de contraste (accesibilidad)

`#EC0029` es un rojo saturado: úsalo como **fondo** con texto blanco
encima (botones, headers), nunca como color de texto sobre fondo claro
— el contraste no es confiable para párrafos largos. Para texto sobre
fondo claro, usa `#1F1F1F` (texto principal) o `#6A6867` (texto
secundario/atenuado).

## Tipografía

Banorte no tiene una tipografía de marca de uso libre públicamente
disponible (su logotipo usa un trazo custom, no una familia tipográfica
que se pueda licenciar/instalar). Para el proyecto se usa una familia
sans-serif del sistema — gratis, sin licencias que gestionar el día del
hackathon, y con buen soporte de acentos/ñ para español:

```
-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif
```

Si más adelante el equipo consigue el manual de marca oficial con la
tipografía real de Banorte, se reemplaza aquí y en el CSS sin tocar
nada más (todo pasa por la variable `--a2ui-font-family-title`).

### Escala tipográfica (ya en uso, sin cambios)

| Token | Tamaño | Uso |
|---|---|---|
| `--a2ui-font-size-xs` | 12px | Metadatos, etiquetas pequeñas |
| `--a2ui-font-size-s` | 14px | Texto secundario, labels de formulario |
| `--a2ui-font-size-m` | 16px | Cuerpo de texto por defecto |
| `--a2ui-font-size-l` | 20px | Subtítulos, encabezados de tarjeta |
| `--a2ui-font-size-xl` | 24px | Títulos de pantalla |
| `--a2ui-font-size-2xl` | 32px | Título principal (ej. "me-alcanza" en login) |

## Aplicación en React (`frontend/src/index.css`)

Estas son las variables CSS actuales (`html:root` en
`frontend/src/index.css`) reescritas con la paleta de Banorte. `@a2ui/web_core`
lee estas mismas variables para pintar los componentes que genera el
LLM (`Card`, `Button`, `Text`, etc.), así que cambiarlas aquí también
re-pinta la UI generativa sin tocar el prompt del backend.

```css
html:root {
  --a2ui-color-primary: #ec0029;
  --a2ui-color-secondary: #6a6867;
  --a2ui-color-background: #f5f5f5;
  --a2ui-color-surface: #ffffff;
  --a2ui-color-border: #c7c9c9;
  --a2ui-color-input: #ffffff;
  --a2ui-color-on-background: #1f1f1f;
  --a2ui-color-on-surface: #1f1f1f;
  --a2ui-color-on-primary: #ffffff;
  --a2ui-color-on-secondary: #ffffff;
  --a2ui-color-on-input: #1f1f1f;
  --a2ui-border-radius: 12px;
  --a2ui-border-width: 1px;
  --a2ui-font-family-title: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --a2ui-font-family-monospace: 'SFMono-Regular', Consolas, monospace;
  --a2ui-font-size-xs: 12px;
  --a2ui-font-size-s: 14px;
  --a2ui-font-size-m: 16px;
  --a2ui-font-size-l: 20px;
  --a2ui-font-size-xl: 24px;
  --a2ui-font-size-2xl: 32px;
  --a2ui-font-scale: 1;
  --a2ui-line-height-body: 1.5;
  --a2ui-line-height-headings: 1.2;
  --a2ui-grid-base: 8px;
  --a2ui-spacing-xs: 4px;
  --a2ui-spacing-s: 8px;
  --a2ui-spacing-m: 16px;
  --a2ui-spacing-l: 24px;
  --a2ui-spacing-xl: 32px;

  /* Acentos opcionales (no forman parte del catálogo estándar de a2ui-web_core;
     defínelos aquí para usarlos en componentes propios si hacen falta). */
  --color-accent-yellow: #f8d44c;
  --color-accent-blue: #108dcd;
}
```

Los colores semánticos (`.login-error`, `.chat-error`) deben usar el
rojo de error (`#c5221f`), no el rojo de marca — así un mensaje de
error nunca se confunde visualmente con un botón o acento de Banorte.
Ya están hardcodeados así en el CSS actual (`#b3261e`); ajustarlos a
`#c5221f` para alinear con esta tabla es un cambio de una línea, no
crítico.

## Aplicación en Flutter (si se construye)

Mapeo directo de estos mismos tokens a un `ThemeData`/`ColorScheme` de
Material 3:

```dart
final colorScheme = ColorScheme.fromSeed(
  seedColor: const Color(0xFFEC0029), // rojo Banorte
  primary: const Color(0xFFEC0029),
  onPrimary: Colors.white,
  secondary: const Color(0xFF6A6867),
  onSecondary: Colors.white,
  surface: Colors.white,
  onSurface: const Color(0xFF1F1F1F),
  error: const Color(0xFFC5221F),
);

final theme = ThemeData(
  colorScheme: colorScheme,
  scaffoldBackgroundColor: const Color(0xFFF5F5F5),
  fontFamily: null, // usa la fuente del sistema (San Francisco / Roboto)
  useMaterial3: true,
);
```

## Qué NO hacer

- No uses el rojo de marca (`#EC0029`) para texto de error — ya hay un
  rojo de error dedicado (`#C5221F`) precisamente para que ambos
  significados no se confundan visualmente.
- No inventes un tono de rojo distinto "porque se ve mejor" — si el
  rojo de marca no funciona en algún componente, es una señal de que
  ese componente necesita otro color (gris, blanco), no un rojo nuevo.
- No mezcles blanco puro (`#FFFFFF`) y blanco técnico (`#F5F5F5`) sin
  criterio: `#F5F5F5` es el fondo de la página, `#FFFFFF` es para lo
  que debe "flotar" sobre ese fondo (tarjetas, inputs, modales).
