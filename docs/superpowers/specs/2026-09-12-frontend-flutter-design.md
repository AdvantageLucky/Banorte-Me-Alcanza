# Diseño: Frontend Flutter (Android) — me-alcanza

## Objetivo

Cliente Flutter que consume el mismo backend FastAPI ya construido (sin
cambios), con paridad funcional completa con el frontend React: login,
chat con renderizado A2UI vía `genui`, y confirmación de acciones
(apartado de ahorro / transferencia con desambiguación). Target
principal: Android (emulador o dispositivo físico).

Este es el cuarto y último entregable de los cuatro planeados en el
spec original (`2026-09-11-me-alcanza-design.md`): MCP server →
backend → React → **Flutter**.

## Alcance

**Incluido:**

- App Flutter con navegación por 3 tabs (`BottomNavigationBar`):
  **Dashboard**, **Chat**, **Yo** — en ese orden visual, con **Chat
  como tab inicial** (es la única que se demuestra hoy).
- **Chat**: login con los mismos usuarios demo (`ana`/`pass123`,
  `luis`/`pass456`), transcripción de conversación (burbujas del
  usuario + tarjetas A2UI del agente, apiladas cronológicamente — igual
  que el fix ya aplicado en React, construido bien desde el día uno acá
  en vez de repetir el mismo bug), y confirmación de acciones
  (`confirmar_accion` → `POST /api/confirm-action`).
- **Dashboard** y **Yo**: pantallas placeholder (ej. "Próximamente"),
  sin lógica de negocio. Existen para que la navegación de 3 tabs esté
  completa, pero no se construyen ni se prueban a fondo en este plan.
- Persistencia del JWT entre sesiones (`shared_preferences`).
- Nueva tool `get_apartados` en el MCP (lectura de apartados activos de
  una cuenta) — hallazgo pendiente de la revisión final del plan del
  MCP server, no relacionado con Flutter en sí pero necesario si más
  adelante "Yo" deja de ser placeholder. **Se agrega en este plan solo
  si el tiempo lo permite; no es requisito para que Chat funcione.**

**Excluido (fuera de alcance para hoy):**

- Cualquier funcionalidad real en Dashboard o Yo (lectura o escritura).
  Explícitamente decidido: "lo dejamos por ahora como placeholder".
- iOS, Flutter Web, Linux desktop — el entorno de desarrollo no tiene
  Chrome configurado y el objetivo de demo es Android.
- Cualquier endpoint nuevo de escritura directa (bypass del LLM) — no
  se construye mientras Yo sea placeholder.
- Tests de integración automatizados contra un emulador Android real
  (no hay uno configurado en este entorno de desarrollo) — se prueban
  los módulos Dart puros con `flutter test`, y la integración real se
  verifica manualmente en un emulador/dispositivo que el equipo
  configure.

## Riesgo técnico declarado por adelantado

`genui` (el framework de Google para UI generativa en Flutter) es,
según su propio README, **"altamente experimental"**. Se investigó su
código fuente real (no solo la documentación de pub.dev, que es
insuficiente) y se confirmó:

- El patrón de inicialización correcto es `SurfaceController(catalogs:
  [CoreCatalogItems.asCatalog()])` + `A2uiTransportAdapter(onSend:
  ...)` + `Conversation(controller: ..., transport: ...)`.
- `A2uiTransportAdapter` acepta un callback `onSend` **completamente
  personalizado** — no depende de `genui_a2ui` (paquete conector
  **descontinuado**, atado a una versión vieja de `genui`) ni de
  `genui_a2a` (paquete conector vigente, pero diseñado para el
  protocolo Agent2Agent de Google sobre WebSocket contra un servidor
  A2A específico — incompatible con nuestro backend REST simple sin
  construir un servidor A2A completo, que está fuera de alcance).
  **Se usa `A2uiTransportAdapter` directo, con un `onSend` propio que
  llama a nuestro `POST /api/chat` — ningún paquete conector de
  terceros.**
- El esquema de mensajes de `genui` (`a2uiMessageSchema()`, en
  `package:genui`) coincide exactamente con lo que ya emite el backend:
  `version: "v0.9"`, `createSurface` / `updateComponents` /
  `updateDataModel` / `deleteSurface`.
- **No se pudo confirmar con certeza vía documentación pública** cómo
  se capturan las acciones de botón (equivalente a nuestro
  `confirmar_accion`) de vuelta hacia el código Dart, ni la firma
  exacta del parseo JSON→`A2uiMessage` (la clase vive en
  `package:a2ui_core`, cuya documentación pública no expone el detalle).

**Por esto, la Task 1 del plan de implementación es una tarea de
verificación contra el código fuente real instalado (leer los archivos
`.dart` del paquete ya descargado en el proyecto vía `dart pub get`),
antes de escribir cualquier lógica de integración — el mismo patrón que
ya usamos cuando el SDK `mcp` de Python resultó comportarse distinto a
lo documentado.**

**Alternativa considerada y descartada:** existe un paquete llamado
literalmente `a2ui_flutter` ("The A2UI Flutter SDK", del mismo equipo
labs.flutter.dev). Se descarta para este plan porque está en fase
`0.0.1-wip002`, su README es literalmente "TODO: add readme", y no
expone ningún catálogo de componentes ni documentación de cómo
renderizar o conectar a un backend — inviable bajo presión de tiempo de
hackathon. Revisar de nuevo si madura después del evento.

## Arquitectura

```
┌─────────────────────────┐   POST /api/login              ┌──────────────────────┐
│  Flutter (Android)       │ ─────────────────────────────> │   Backend FastAPI      │
│  genui (SurfaceController│ <───────────────────────────── │   (sin cambios —       │
│  + A2uiTransportAdapter  │   POST /api/chat                │    ya construido)      │
│  con onSend propio)      │   POST /api/confirm-action     │                       │
│  shared_preferences (JWT)│                                 │                       │
└─────────────────────────┘                                 └──────────────────────┘
```

Cero cambios al backend salvo, opcionalmente, `get_apartados` (ver
Alcance). Mismo contrato exacto que React: `{token}` en login,
`{a2ui_messages: [...]}` en chat/confirm-action, mismo evento
`confirmar_accion` con `context.proposalId`.

## Componentes

### 1. Estructura del proyecto

```
flutter_app/
  lib/
    main.dart
    api/
      api_client.dart       # login/sendMessage/confirmAction (espejo de api/client.js)
    auth/
      auth_repository.dart  # persistencia del JWT (shared_preferences)
      auth_provider.dart    # estado de sesión (ChangeNotifier)
    chat/
      chat_screen.dart      # transcripción + input + integración genui
      action_router.dart    # detecta confirmar_accion, llama confirmAction
    shell/
      app_shell.dart        # BottomNavigationBar con las 3 tabs
    dashboard/
      dashboard_placeholder_screen.dart
    yo/
      yo_placeholder_screen.dart
    login/
      login_screen.dart
  test/
    api/api_client_test.dart
    auth/auth_repository_test.dart
    chat/action_router_test.dart
```

### 2. `ApiClient` (`lib/api/api_client.dart`)

Espejo exacto de `frontend/src/api/client.js`: mismo shape de
requests/respuestas, mismo manejo de errores.

```dart
class ApiException implements Exception {
  ApiException(this.statusCode, this.detail);
  final int statusCode;
  final String? detail;
}

class ApiClient {
  ApiClient(this.baseUrl, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  final String baseUrl;
  final http.Client _http;

  Future<String> login(String username, String password) async {
    final body = await _post('/api/login', body: {
      'username': username,
      'password': password,
    });
    return body['token'] as String;
  }

  Future<List<dynamic>> sendMessage(String token, String mensaje) async {
    final body = await _post(
      '/api/chat',
      body: {'mensaje': mensaje},
      token: token,
    );
    return body['a2ui_messages'] as List<dynamic>;
  }

  Future<List<dynamic>> confirmAction(String token, String proposalId) async {
    final body = await _post(
      '/api/confirm-action',
      body: {'proposal_id': proposalId},
      token: token,
    );
    return body['a2ui_messages'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
    String? token,
  }) async {
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final response = await _http.post(
      Uri.parse('$baseUrl$path'),
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String? detail;
      try {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        detail = decoded['detail'] as String?;
      } catch (_) {
        detail = null;
      }
      throw ApiException(response.statusCode, detail);
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
```

### 3. `AuthRepository` (`lib/auth/auth_repository.dart`)

Espejo de `auth/tokenStorage.js`, usando `shared_preferences` en vez de
`localStorage`.

```dart
class AuthRepository {
  static const _tokenKey = 'me_alcanza_token';

  Future<String?> readToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  Future<void> writeToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  Future<void> clearToken() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }
}
```

### 4. Integración `genui` en `ChatScreen`

Sujeto a que la Task 1 (verificación) confirme los nombres exactos.
Diseño esperado, basado en el código real del README de `genui`:

- `SurfaceController(catalogs: [CoreCatalogItems.asCatalog()])`.
- `A2uiTransportAdapter(onSend: _onSend)`, donde `_onSend` llama a
  `apiClient.sendMessage(token, mensaje)` y alimenta cada mensaje de la
  respuesta al transporte (método exacto a confirmar en Task 1 —
  candidato: `_transport.addMessage(A2uiMessage.fromJson(msg))` por
  cada elemento de la lista, ya que el backend entrega el bloque A2UI
  completo de una vez, no como texto incremental que necesite
  `addChunk`/parseo).
- `Conversation(controller: _controller, transport: _transport)`,
  escuchando `_conversation.events` para saber cuándo se agregó una
  superficie nueva (`ConversationSurfaceAdded`) y así hacer *append* a
  la lista de turnos — el mismo patrón de transcripción que ya
  construimos en React (cada turno es una entrada nueva, nunca se
  sobreescribe una anterior).
- Cómo se capturan los clics de botón (`confirmar_accion`) hacia
  `action_router.dart` es exactamente lo que la Task 1 debe determinar
  leyendo el código fuente instalado — no se asume una API aquí.

### 5. `action_router.dart`

Espejo de `chat/actionHandler.js`: recibe una acción, verifica que el
nombre sea `confirmar_accion`, extrae `context['proposalId']`, llama
`apiClient.confirmAction`, y alimenta la respuesta de vuelta al mismo
`Conversation`/`SurfaceController` (agregando un turno nuevo a la
transcripción, igual que un mensaje de chat normal).

### 6. `AppShell` — navegación de 3 tabs

```dart
class AppShell extends StatefulWidget {
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _currentIndex = 1; // Chat es el tab inicial

  static const _screens = [
    DashboardPlaceholderScreen(),
    ChatScreen(),
    YoPlaceholderScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.chat_bubble_outline), label: 'Chat'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'Yo'),
        ],
      ),
    );
  }
}
```

`DashboardPlaceholderScreen`/`YoPlaceholderScreen` son widgets triviales
(`Center(child: Text('Próximamente'))`), sin tests — no hay lógica que
probar.

### 7. Tema visual

Aplica la paleta de `docs/design-system.md` (rojo Banorte `#EC0029`,
blancos/grises) vía `ThemeData`/`ColorScheme.fromSeed`, tal como ya está
documentado ahí en la sección "Aplicación en Flutter".

## Flujo de datos (idéntico a React, solo cambia el cliente)

1. Login → `POST /api/login` → JWT guardado en `shared_preferences`.
2. Usuario escribe en `ChatScreen` → `ApiClient.sendMessage` →
   `onSend` del transporte alimenta la respuesta a `genui` → se agrega
   un turno nuevo a la transcripción con la superficie renderizada.
3. Usuario toca un botón de confirmación → `action_router` intercepta
   → `ApiClient.confirmAction` → respuesta se agrega como turno nuevo.
4. Un 401 en cualquier llamada → limpia el token → regresa a
   `LoginScreen` (igual que `handleApiError` en React).

## Manejo de errores

- Red no disponible / backend caído: `ApiException` sin `statusCode`
  HTTP real (excepción de socket) → mensaje genérico "No se pudo
  contactar el servidor", igual que el fix ya aplicado en
  `LoginView.jsx`.
- 401 en `/api/chat` o `/api/confirm-action`: limpia sesión, regresa a
  login.
- Bloque A2UI inválido o error del backend: el backend ya lo maneja
  (siempre devuelve un bloque A2UI de error legible, nunca un 500
  crudo) — Flutter solo necesita renderizarlo como cualquier otro turno
  del agente, sin lógica especial.

## Testing

- **Unitarios (Dart puro, `flutter test`)**: `ApiClient` (mock de
  `http.Client`, mismos casos que `client.test.js`: login exitoso, chat
  con token, confirm-action, error 401 con detail, error sin JSON
  parseable), `AuthRepository` (round-trip de token usando
  `SharedPreferences.setMockInitialValues` para no tocar disco real),
  `action_router` (ignora acciones que no sean `confirmar_accion`,
  llama confirmAction con el proposalId correcto, no revienta si el
  backend falla).
- **Sin tests automatizados de widgets/integración** — `ChatScreen` y
  `AppShell` se verifican manualmente en un emulador/dispositivo
  Android, igual que `ChatView.jsx`/`LoginView.jsx` en React (mismo
  criterio: sin backend simulado con mocks a nivel de widget, se prueba
  contra el backend real).

## Configuración

`flutter_app/.env` — Flutter no tiene soporte nativo de `.env` como
Vite; se usa el paquete `flutter_dotenv` o, más simple para una demo,
una constante en `lib/config.dart` con `String.fromEnvironment` /un
valor default `http://10.0.2.2:8000` (la IP que el emulador Android usa
para referirse a `localhost` de la máquina host — **no** `localhost`
directo, que en el emulador se refiere al propio dispositivo virtual).
Este detalle de red del emulador Android se documenta explícitamente en
el plan para que no sea una sorpresa al probar. Si en vez de emulador
se usa un celular físico, `10.0.2.2` no aplica — hay que usar la IP de
red local de la laptop que corre el backend (ej. `192.168.x.x`) y que
el celular esté en la misma red Wi-Fi; esto se documenta en el
`README.md` del proyecto Flutter, no se resuelve automáticamente.

## Fuera de este spec (posible follow-up, no hoy)

- Funcionalidad real en Dashboard y Yo (lectura en vivo del backend +
  posible escritura directa).
- `get_apartados` en el MCP (identificado como gap, no bloqueante).
- iOS / Flutter Web.
- Tests de integración automatizados con `integration_test` contra un
  emulador en CI.
