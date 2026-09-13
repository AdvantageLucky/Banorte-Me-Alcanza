# Me alcanza — cliente Flutter (Android)

Segundo cliente del mismo backend: consume exactamente el mismo stream
A2UI que el frontend web (`POST /api/chat`, `POST /api/confirm-action`)
y lo renderiza con `genui` + `a2ui_core`. Es la prueba de que la
interfaz *viaja* ([ADR 0012](../docs/adr/0012-dos-clientes-mismo-stream-a2ui.md)).

## Pestañas

| Pestaña | Qué hace | Estado |
|---|---|---|
| **Sugerencias** | Tarjetas A2UI que el backend arma solo, sin que el usuario pregunte (`GET /api/sugerencias`). Atender / Descartar van al REST. Historial colapsado. Badge con pendientes en la barra. | Hecho |
| **Asistente** | Chat con UI generativa; conserva el hilo (`conversacion_id`) entre turnos; botón para abrir un hilo nuevo; tres preguntas sugeridas al inicio. | Hecho |
| **Yo** | Un solo scroll: saldo + **riel de la quincena** (hoy → próxima nómina con los pagos fijos marcados), score de salud, y CRUD completo de pagos fijos, ingresos, metas (+ apartar / cancelar apartado), contactos y movimientos. Todo se edita en bottom sheets; deslizar para eliminar. | Hecho |

**Pendiente — concepto bandera:** debajo de cada tarjeta de Sugerencias
irá la propuesta de solución generada por el LLM para esa situación
concreta, sin que el usuario teclee. El punto de extensión está
marcado en `lib/sugerencias/sugerencias_screen.dart` (`_PendienteTile`).

## Estructura

```
lib/
├── a2ui/a2ui_host.dart        plomería genui compartida (chat y sugerencias)
├── a2ui/me_alcanza_catalog.dart  catálogo propio: básico + StatCard, BarChart, PlanDePago
├── api/api_client.dart        un método por endpoint REST
├── models/models.dart         formas de los recursos
├── theme/                     tokens de marca + ThemeData (BankGothic para cifras)
├── shared/                    formateadores es-MX, widgets comunes
├── sugerencias/               controller, router de acciones, pantalla
├── chat/                      pantalla del asistente + router de confirmar_accion
├── yo/                        controller, riel de quincena, secciones, sheets, validadores
├── login/  shell/  auth/
└── config.dart                API_BASE_URL
```

## Catálogo A2UI propio

El backend emite superficies con el `catalogId`
`https://me-alcanza.hackmty.dev/catalogs/v1/catalog.json` y siete componentes
de dominio (StatCard, BarChart, PlanDePago, LineChart, ApartadoPlanner,
DonutChart, BudgetAllocator) además de los básicos. `genui` renderiza **"Catalog not found"**
si ese id no está registrado, así que `lib/a2ui/me_alcanza_catalog.dart`
debe mantenerse en sync a mano con `src/me_alcanza/backend/a2ui_custom_catalog.py`
y `frontend/src/a2ui-custom/`: mismo id, mismos nombres, mismas props. El
test `test/a2ui/me_alcanza_catalog_test.dart` levanta un `SurfaceController`
real con ese id y falla si algo se desalinea.

## Requisitos

- Flutter 3.44+ / Dart 3.12+.
- El backend corriendo (ver raíz del repo: `uv run me-alcanza`), o el
  público en `https://homelab.tail8dc7f1.ts.net`.

## Configuración de red

- **Emulador Android**: valor por defecto `http://10.0.2.2:8000`
  (`10.0.2.2` es el `localhost` de la laptop visto desde el emulador).
- **Celular físico**: misma red Wi-Fi que la laptop, y su IP local:
  ```bash
  flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000
  ```
- **Backend público**:
  ```bash
  flutter run --dart-define=API_BASE_URL=https://homelab.tail8dc7f1.ts.net
  ```

## Uso

```bash
cd flutter_app
flutter pub get
flutter run
```

Cuentas demo: `ana` / `pass123`, `luis` / `pass456`.

## Pruebas

```bash
flutter analyze
flutter test
```

Unitarios sobre los módulos puros: `ApiClient` (todos los endpoints,
incluidos errores 400/422), formateadores, validadores, el modelo del
riel de la quincena, `SugerenciasController` y los routers de acciones.
Widget tests del riel y de los siete componentes del catálogo propio
(renderizados por un `SurfaceController` real). Las pantallas se
verifican a mano en un emulador, dispositivo o con `flutter build web`.

## Verificación manual antes de la demo

1. **Sugerencias**: entra como `ana`. Deben aparecer 4 tarjetas de pago
   próximo (Agua, Luz, dos colegiaturas). Descarta una: pasa al
   historial y el badge baja a 3.
2. **Yo**: el saldo dice `$500.00`, la frase "Mañana cobras $12,500" y
   el riel muestra la nómina al final. Agrega un pago fijo con fecha
   antes de la nómina: aparece como marca roja en el riel. En la meta
   "Concierto", toca **Apartar**, deja `$142.50` semanal y activa: el
   saldo baja a `$357.50` animado y aparece el movimiento.
3. **Asistente**: pregunta "¿me alcanza para el concierto del 13 de
   octubre?"; debe aparecer el veredicto con botón de apartado. Después
   escribe "y si fueran 5,000": debe responder con memoria del hilo.
