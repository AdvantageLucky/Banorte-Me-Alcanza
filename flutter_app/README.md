# me-alcanza — frontend Flutter (Android)

Cliente Flutter con paridad funcional completa con el frontend React:
login, chat con UI generativa (A2UI vía `genui`), y confirmación de
acciones (apartado de ahorro / transferencia). Navegación de 3 tabs
(Dashboard, Chat, Yo) — **solo Chat es funcional hoy**; Dashboard y Yo
son placeholders deliberados (ver
`docs/superpowers/specs/2026-09-12-frontend-flutter-design.md`).

## Requisitos

- Flutter 3.44+ / Dart 3.12+.
- El backend corriendo (ver raíz del repo: `uv run me-alcanza`).
- Un emulador Android (`flutter emulators --launch <id>`) o un celular
  físico conectado por USB con depuración habilitada.

## Configuración de red — IMPORTANTE

- **Emulador Android**: usa el valor por defecto
  (`http://10.0.2.2:8000`) — `10.0.2.2` es cómo el emulador ve el
  `localhost` de la laptop que lo corre. No cambiar nada.
- **Celular físico**: `10.0.2.2` NO funciona. Corre
  `hostname -I` (Linux) o revisa tu IP de red local (ej.
  `192.168.1.50`), asegúrate de que el celular esté en la misma red
  Wi-Fi que la laptop, y lanza la app con:
  ```bash
  flutter run --dart-define=API_BASE_URL=http://192.168.1.50:8000
  ```

## Uso

```bash
cd flutter_app
flutter pub get
flutter run
```

Usuarios demo: `ana`/`pass123`, `luis`/`pass456`.

## Pruebas

```bash
cd flutter_app
flutter test
```

Corre los tests unitarios de los módulos Dart puros (`ApiClient`,
`AuthRepository`, `ActionRouter`). Las pantallas (`LoginScreen`,
`ChatScreen`, `AppShell`) se verifican manualmente en un
emulador/dispositivo — ver los dos flujos abajo.

## Verificación manual de los dos flujos núcleo

Con el backend corriendo y la app instalada en el emulador/dispositivo:

1. **Afford-check + apartado**: inicia sesión como `ana`/`pass123`,
   escribe "¿me alcanza para el concierto del 13 de octubre?". Debe
   aparecer una tarjeta con el veredicto y, si no alcanza, un botón
   para activar el apartado sugerido.
2. **Transferencia con desambiguación**: escribe "deposítale 500 a mi
   hermano Pepe". Deben aparecer dos tarjetas de confirmación (dos
   contactos candidatos).

Ambos flujos deben sobrevivir cerrar y volver a abrir la app sin perder
la sesión (el token persiste vía `shared_preferences`).

## Estado de verificación en este entorno de desarrollo

- `flutter test`: corrido y verificado en este entorno (12/12 tests).
- `flutter build apk --debug`: corrido y verificado en este entorno
  (compila con éxito, genera el APK real incluyendo la integración de
  `genui`).
- Verificación manual end-to-end (los dos flujos de arriba, en un
  emulador/dispositivo real contra el backend real): **no realizada en
  este entorno** — no hay ningún dispositivo/emulador Android
  disponible aquí (`flutter devices` no lista ninguno; el toolchain de
  Android tiene licencias sin aceptar). Esta verificación queda
  pendiente para que el equipo la corra en su propia máquina/dispositivo
  antes de la demo, siguiendo los pasos de la sección anterior.
