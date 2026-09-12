# Frontend Flutter (Android) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el cliente Flutter (`flutter_app/`) que consume el backend FastAPI ya existente sin cambios: login, chat con renderizado A2UI vía `genui`, confirmación de acciones, y navegación de 3 tabs (Dashboard/Chat/Yo, solo Chat funcional).

**Architecture:** Bottom-up, igual que los planes anteriores: primero los módulos Dart puros y testeables (`ApiClient`, `AuthRepository`, `ActionRouter`) sin ninguna dependencia de `genui`, luego las pantallas (Login, Chat con la integración `genui`, el shell de navegación), y al final el tema visual y la verificación manual. La Task 1 es una tarea de investigación/verificación contra el código fuente real de `genui` — no se asume la API antes de confirmarla.

**Tech Stack:** Flutter 3.44 / Dart 3.12 (ya instalados en este entorno), `genui ^0.10.3` (UI generativa), `http ^1.6.0`, `shared_preferences ^2.5.5`, `flutter_test` (incluido con Flutter).

**Spec:** `docs/superpowers/specs/2026-09-12-frontend-flutter-design.md`

## Global Constraints

- Sin routing por URL — navegación por `BottomNavigationBar` con 3 tabs (Dashboard, Chat, Yo), **Chat es el tab inicial**.
- Dashboard y Yo son placeholders (`Center(child: Text('Próximamente'))`) — sin lógica, sin tests.
- `genui_a2ui` y `genui_a2a` **no se usan** — son incompatibles/deprecados (ver spec). Se usa `genui` directo con un `A2uiTransportAdapter` de `onSend` propio.
- El emulador Android usa `10.0.2.2` para referirse a `localhost` de la máquina host — nunca `localhost` directo.
- Mismos usuarios demo que React: `ana`/`pass123`, `luis`/`pass456`.
- Mismo contrato de API que React, sin cambios al backend: `POST /api/login`, `POST /api/chat`, `POST /api/confirm-action`; único evento de acción `confirmar_accion` con `context.proposalId`.
- Paleta de color: `docs/design-system.md` (rojo Banorte `#EC0029` + blancos/grises).

---

### Task 1: Scaffold del proyecto Flutter + verificación de la API real de `genui`

**Contexto:** `genui` es "altamente experimental" según su propio README. Ya se confirmó el patrón de inicialización básico (`SurfaceController` + `A2uiTransportAdapter` + `Conversation`) leyendo el README real del paquete, pero **no** cómo se capturan las acciones de botón de vuelta a Dart, ni la firma exacta de `A2uiMessage.fromJson`. Esta tarea produce un documento de hallazgos (`flutter_app/GENUI_API_NOTES.md`) que la Task 6 debe leer antes de escribir la integración del chat.

**Files:**
- Create: `flutter_app/` (vía `flutter create`)
- Modify: `flutter_app/pubspec.yaml`
- Create: `flutter_app/GENUI_API_NOTES.md`

**Interfaces:**
- Produces: proyecto Flutter que compila (`flutter analyze` sin errores, `flutter test` corre — aunque sin tests todavía), y el documento de hallazgos que las Tasks 6 y 7 consumen.

- [ ] **Step 1: Crear el proyecto**

Desde la raíz del repo:

```bash
flutter create --org com.banorte.mealcanza --project-name me_alcanza flutter_app
cd flutter_app
```

- [ ] **Step 2: Agregar las dependencias**

Editar `flutter_app/pubspec.yaml`, en la sección `dependencies:` (debajo de `flutter:` y `cupertino_icons:` que ya trae el scaffold), agregar:

```yaml
  genui: ^0.10.3
  http: ^1.6.0
  shared_preferences: ^2.5.5
```

- [ ] **Step 3: Instalar dependencias**

```bash
flutter pub get
```

Expected: termina sin errores, actualiza `pubspec.lock`.

- [ ] **Step 4: Ubicar el paquete `genui` instalado**

```bash
dart pub cache list 2>/dev/null | grep genui || find "$HOME/.pub-cache/hosted" -maxdepth 2 -iname "genui-*" -type d
```

Anotar la ruta exacta que imprime (ej.
`$HOME/.pub-cache/hosted/pub.dev/genui-0.10.3`) — se usa en los
siguientes steps como `$GENUI_PATH`.

- [ ] **Step 5: Investigar cómo se parsea JSON crudo a `A2uiMessage`**

```bash
GENUI_PATH="<la ruta del Step 4>"
grep -rn "fromJson" "$GENUI_PATH/lib" | grep -i "a2ui\|message" | head -20
```

Buscar específicamente una función o factory que reciba un
`Map<String, dynamic>` (el resultado de `jsonDecode` de un elemento de
`a2ui_messages`) y devuelva algo aceptado por `addMessage` en
`A2uiTransportAdapter`. Si `genui` no expone esto directamente, buscar
en `a2ui_core` (mismo comando, apuntando a
`$HOME/.pub-cache/hosted/pub.dev/a2ui_core-*/lib`).

- [ ] **Step 6: Investigar cómo se capturan las acciones de botón (equivalente a `confirmar_accion`)**

```bash
grep -rn "class Conversation" "$GENUI_PATH/lib" -A 30 | head -80
grep -rn "Action" "$GENUI_PATH/lib/src" | grep -iv "test" | head -40
```

Buscar específicamente: ¿el evento de acción llega por
`_conversation.events` (como un tipo `ConversationAction...`), por un
callback separado en el constructor de `Conversation`/`SurfaceController`,
o por algo que expone `A2uiTransportAdapter`? Anotar el nombre exacto
de la clase/callback y su forma (qué campos trae — debe incluir, en
algún lado, el nombre de la acción y el `context` con `proposalId`).

- [ ] **Step 7: Escribir `flutter_app/GENUI_API_NOTES.md` con los hallazgos**

Documento con esta estructura (rellenar con lo encontrado en los Steps
5-6 — nombres de clases, métodos, y un snippet corto de la firma real
copiada del código fuente, no inventada):

```markdown
# Hallazgos de la API real de genui (verificado contra el código fuente)

Versión instalada: <la del Step 4>

## Parseo JSON -> A2uiMessage

<Cómo se hace exactamente, con el nombre real de la clase/método>

## Captura de acciones de botón (confirmar_accion)

<Cómo se hace exactamente, con el nombre real de la clase/evento>

## Widget Surface — parámetros exactos del constructor

<Copiar la firma real de la clase Surface encontrada en el código>
```

- [ ] **Step 8: Verificar que el proyecto compila**

```bash
flutter analyze
```

Expected: sin errores (warnings del scaffold por defecto son aceptables).

- [ ] **Step 9: Commit**

```bash
git add flutter_app/
git commit -m "chore: scaffold Flutter project and document genui integration findings"
```

---

### Task 2: `ApiClient` — cliente HTTP puro (espejo de `api/client.js`)

**Files:**
- Create: `flutter_app/lib/api/api_client.dart`
- Test: `flutter_app/test/api/api_client_test.dart`

**Interfaces:**
- Consumes: nada (módulo puro, solo depende de `package:http`).
- Produces: `class ApiException implements Exception { final int statusCode; final String? detail; }`,
  `class ApiClient { ApiClient(String baseUrl, {http.Client? httpClient});
  Future<String> login(String username, String password);
  Future<List<dynamic>> sendMessage(String token, String mensaje);
  Future<List<dynamic>> confirmAction(String token, String proposalId); }`.

- [ ] **Step 1: Escribir los tests**

```dart
// flutter_app/test/api/api_client_test.dart
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:me_alcanza/api/api_client.dart';

class _FakeHttpClient extends http.BaseClient {
  _FakeHttpClient(this.handler);
  final Future<http.StreamedResponse> Function(http.BaseRequest) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) =>
      handler(request);
}

http.StreamedResponse _jsonResponse(int statusCode, Map<String, dynamic> body) {
  final bytes = utf8.encode(jsonEncode(body));
  return http.StreamedResponse(Stream.value(bytes), statusCode);
}

void main() {
  group('ApiClient', () {
    test('posts credentials to /api/login and returns the token', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'token': 'jwt-123'});
        }),
      );

      final token = await client.login('ana', 'pass123');

      expect(token, 'jwt-123');
      expect(captured!.url.toString(), 'http://api.test/api/login');
      expect(captured!.method, 'POST');
      expect(captured!.headers['Content-Type'], 'application/json');
      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'username': 'ana', 'password': 'pass123'});
    });

    test('sends the bearer token and mensaje on /api/chat', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.sendMessage('jwt-123', '¿me alcanza para el concierto?');

      expect(captured!.headers['Authorization'], 'Bearer jwt-123');
      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'mensaje': '¿me alcanza para el concierto?'});
    });

    test('sends proposal_id on /api/confirm-action', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.confirmAction('jwt-123', 'prop-1');

      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'proposal_id': 'prop-1'});
    });

    test('throws an ApiException carrying the backend detail on a non-2xx response',
        () async {
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          return _jsonResponse(401, {'detail': 'Usuario o contraseña incorrectos'});
        }),
      );

      await expectLater(
        client.login('ana', 'wrong'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.detail, 'detail', 'Usuario o contraseña incorrectos'),
        ),
      );
    });

    test('falls back to a null detail when the error body is not JSON', () async {
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          final bytes = utf8.encode('not json');
          return http.StreamedResponse(Stream.value(bytes), 500);
        }),
      );

      await expectLater(client.login('ana', 'x'), throwsA(isA<ApiException>()));
    });
  });
}
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd flutter_app && flutter test test/api/api_client_test.dart`
Expected: FAIL — `Error: Not found: 'package:me_alcanza/api/api_client.dart'`.

- [ ] **Step 3: Implementar `lib/api/api_client.dart`**

```dart
// flutter_app/lib/api/api_client.dart
import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.statusCode, this.detail);

  final int statusCode;
  final String? detail;

  @override
  String toString() => detail ?? 'Error HTTP $statusCode';
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

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd flutter_app && flutter test test/api/api_client_test.dart`
Expected: PASS — 5 tests en verde.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/api/api_client.dart flutter_app/test/api/api_client_test.dart
git commit -m "feat: add ApiClient for login/chat/confirm-action"
```

---

### Task 3: `AuthRepository` — persistencia del JWT (espejo de `auth/tokenStorage.js`)

**Files:**
- Create: `flutter_app/lib/auth/auth_repository.dart`
- Test: `flutter_app/test/auth/auth_repository_test.dart`

**Interfaces:**
- Consumes: `package:shared_preferences`.
- Produces: `class AuthRepository { Future<String?> readToken(); Future<void> writeToken(String token); Future<void> clearToken(); }`.

- [ ] **Step 1: Escribir los tests**

```dart
// flutter_app/test/auth/auth_repository_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:me_alcanza/auth/auth_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AuthRepository', () {
    test('returns null when nothing is stored', () async {
      final repo = AuthRepository();
      expect(await repo.readToken(), isNull);
    });

    test('round-trips a token through write/read', () async {
      final repo = AuthRepository();
      await repo.writeToken('jwt-abc');
      expect(await repo.readToken(), 'jwt-abc');
    });

    test('clears a stored token', () async {
      final repo = AuthRepository();
      await repo.writeToken('jwt-abc');
      await repo.clearToken();
      expect(await repo.readToken(), isNull);
    });
  });
}
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd flutter_app && flutter test test/auth/auth_repository_test.dart`
Expected: FAIL — `Error: Not found: 'package:me_alcanza/auth/auth_repository.dart'`.

- [ ] **Step 3: Implementar `lib/auth/auth_repository.dart`**

```dart
// flutter_app/lib/auth/auth_repository.dart
import 'package:shared_preferences/shared_preferences.dart';

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

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd flutter_app && flutter test test/auth/auth_repository_test.dart`
Expected: PASS — 3 tests en verde.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/auth/auth_repository.dart flutter_app/test/auth/auth_repository_test.dart
git commit -m "feat: add AuthRepository for JWT persistence"
```

---

### Task 4: `ActionRouter` — enruta el evento `confirmar_accion` (espejo de `chat/actionHandler.js`)

**Files:**
- Create: `flutter_app/lib/chat/action_router.dart`
- Test: `flutter_app/test/chat/action_router_test.dart`

**Interfaces:**
- Consumes: nada directamente — es un módulo puro que recibe un `Map<String, dynamic>` genérico con la forma `{name, context}` (desacoplado a propósito de la representación real de acción que use `genui`; la Task 6 se encarga de convertir lo que sea que `genui` entregue a esta forma, según lo que documente `GENUI_API_NOTES.md`).
- Produces: `const confirmActionName = 'confirmar_accion';`,
  `class ActionRouter { ActionRouter({required ConfirmActionFn confirmAction, required OnMessagesFn onMessages, required OnErrorFn onError}); Future<void> handle(Map<String, dynamic> action); }`
  con `typedef ConfirmActionFn = Future<List<dynamic>> Function(String proposalId);`,
  `typedef OnMessagesFn = void Function(List<dynamic> messages);`,
  `typedef OnErrorFn = void Function(Object error);`.

- [ ] **Step 1: Escribir los tests**

```dart
// flutter_app/test/chat/action_router_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/chat/action_router.dart';

void main() {
  group('ActionRouter', () {
    test('ignores actions with a name other than confirmar_accion', () async {
      var confirmCalled = false;
      var messagesCalled = false;
      var errorCalled = false;
      final router = ActionRouter(
        confirmAction: (id) async {
          confirmCalled = true;
          return [];
        },
        onMessages: (_) => messagesCalled = true,
        onError: (_) => errorCalled = true,
      );

      await router.handle({
        'name': 'otra_accion',
        'context': {'proposalId': 'prop-1'},
      });

      expect(confirmCalled, isFalse);
      expect(messagesCalled, isFalse);
      expect(errorCalled, isFalse);
    });

    test(
        'confirms the proposal from context.proposalId and forwards the resulting messages',
        () async {
      String? receivedId;
      List<dynamic>? receivedMessages;
      final router = ActionRouter(
        confirmAction: (id) async {
          receivedId = id;
          return [
            {'foo': 'bar'}
          ];
        },
        onMessages: (messages) => receivedMessages = messages,
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedId, 'prop-1');
      expect(receivedMessages, [
        {'foo': 'bar'}
      ]);
    });

    test('reports an error when confirming the proposal fails, without touching onMessages',
        () async {
      final failure = Exception('boom');
      Object? receivedError;
      final router = ActionRouter(
        confirmAction: (id) async => throw failure,
        onMessages: (_) => fail('should not be called'),
        onError: (err) => receivedError = err,
      );

      await router.handle({
        'name': confirmActionName,
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedError, failure);
    });

    test('does nothing when proposalId is missing from context', () async {
      var confirmCalled = false;
      final router = ActionRouter(
        confirmAction: (id) async {
          confirmCalled = true;
          return [];
        },
        onMessages: (_) {},
        onError: (_) => fail('should not be called'),
      );

      await router.handle({'name': confirmActionName, 'context': <String, dynamic>{}});

      expect(confirmCalled, isFalse);
    });
  });
}
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd flutter_app && flutter test test/chat/action_router_test.dart`
Expected: FAIL — `Error: Not found: 'package:me_alcanza/chat/action_router.dart'`.

- [ ] **Step 3: Implementar `lib/chat/action_router.dart`**

```dart
// flutter_app/lib/chat/action_router.dart
const confirmActionName = 'confirmar_accion';

typedef ConfirmActionFn = Future<List<dynamic>> Function(String proposalId);
typedef OnMessagesFn = void Function(List<dynamic> messages);
typedef OnErrorFn = void Function(Object error);

class ActionRouter {
  ActionRouter({
    required this.confirmAction,
    required this.onMessages,
    required this.onError,
  });

  final ConfirmActionFn confirmAction;
  final OnMessagesFn onMessages;
  final OnErrorFn onError;

  Future<void> handle(Map<String, dynamic> action) async {
    if (action['name'] != confirmActionName) {
      return;
    }
    final context = action['context'] as Map<String, dynamic>?;
    final proposalId = context?['proposalId'] as String?;
    if (proposalId == null) {
      return;
    }
    try {
      final messages = await confirmAction(proposalId);
      onMessages(messages);
    } catch (err) {
      onError(err);
    }
  }
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd flutter_app && flutter test test/chat/action_router_test.dart`
Expected: PASS — 4 tests en verde.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/chat/action_router.dart flutter_app/test/chat/action_router_test.dart
git commit -m "feat: add ActionRouter for confirmar_accion events"
```

---

### Task 5: Estado de sesión (`AuthController`) + `LoginScreen`

**Files:**
- Create: `flutter_app/lib/auth/auth_controller.dart`
- Create: `flutter_app/lib/login/login_screen.dart`

**Interfaces:**
- Consumes: `ApiClient` (Task 2), `AuthRepository` (Task 3).
- Produces: `class AuthController extends ChangeNotifier { AuthController({required ApiClient apiClient, required AuthRepository authRepository}); String? get token; Future<void> restoreSession(); Future<void> login(String username, String password); void logout(); }` —
  consumido por `AppShell` (Task 7) y `ChatScreen` (Task 6). `LoginScreen` widget — se muestra cuando `token` es `null`.

No hay tests automatizados para esta tarea (widgets — ver Global
Constraints); verificación manual en el Step 4.

- [ ] **Step 1: Implementar `lib/auth/auth_controller.dart`**

```dart
// flutter_app/lib/auth/auth_controller.dart
import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import 'auth_repository.dart';

class AuthController extends ChangeNotifier {
  AuthController({
    required ApiClient apiClient,
    required AuthRepository authRepository,
  })  : _apiClient = apiClient,
        _authRepository = authRepository;

  final ApiClient _apiClient;
  final AuthRepository _authRepository;

  String? _token;
  String? get token => _token;

  Future<void> restoreSession() async {
    _token = await _authRepository.readToken();
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    final newToken = await _apiClient.login(username, password);
    await _authRepository.writeToken(newToken);
    _token = newToken;
    notifyListeners();
  }

  void logout() {
    _authRepository.clearToken();
    _token = null;
    notifyListeners();
  }
}
```

- [ ] **Step 2: Implementar `lib/login/login_screen.dart`**

```dart
// flutter_app/lib/login/login_screen.dart
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.authController});

  final AuthController authController;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  String? _error;
  bool _submitting = false;

  Future<void> _handleSubmit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.authController.login(
        _usernameController.text,
        _passwordController.text,
      );
    } on ApiException catch (err) {
      setState(() => _error = err.detail ?? 'Usuario o contraseña incorrectos.');
    } catch (_) {
      setState(() => _error = 'No se pudo contactar el servidor.');
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('me-alcanza', style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 24),
                TextField(
                  controller: _usernameController,
                  decoration: const InputDecoration(labelText: 'Usuario'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _passwordController,
                  decoration: const InputDecoration(labelText: 'Contraseña'),
                  obscureText: true,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                ],
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _submitting ? null : _handleSubmit,
                  child: Text(_submitting ? 'Entrando...' : 'Entrar'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 3: Verificar que compila**

Run: `cd flutter_app && flutter analyze`
Expected: sin errores.

- [ ] **Step 4: Verificación manual (best-effort sin emulador en este entorno)**

Si hay un emulador o dispositivo Android conectado
(`flutter devices`), correr `flutter run` apuntando temporalmente
`main.dart` a `LoginScreen` para confirmar que se ve el formulario sin
crashear. Si no hay dispositivo disponible en este entorno de
desarrollo, dejar esta verificación para la Task 9 (verificación
manual final), donde ya existirá la app completa para probar de una
vez en el dispositivo del equipo.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/auth/auth_controller.dart flutter_app/lib/login/login_screen.dart
git commit -m "feat: add AuthController and LoginScreen"
```

---

### Task 6: `ChatScreen` — integración `genui` + transcripción de chat

**Files:**
- Create: `flutter_app/lib/chat/chat_screen.dart`
- Modify: `flutter_app/pubspec.yaml` (agregar `a2ui_core`)

**Interfaces:**
- Consumes: `ApiClient` (Task 2), `ActionRouter`/`confirmActionName` (Task 4), `AuthController` (Task 5), y los hallazgos de `flutter_app/GENUI_API_NOTES.md` (Task 1).
- Produces: `ChatScreen` widget — consumido por `AppShell` (Task 7).

No hay tests automatizados para esta tarea (widget con dependencia de
`genui` — ver Global Constraints); verificación manual en la Task 9.

**Actualizado tras la Task 1** (que ya se ejecutó y verificó
independientemente contra el código fuente real de `genui`): el
borrador original de esta tarea asumía `Surface(host:, surfaceId:)` y
que las acciones de botón llegaban por `_conversation.events` — **ambas
suposiciones eran incorrectas**. El código de abajo ya incorpora los
hallazgos reales de `flutter_app/GENUI_API_NOTES.md`:

- Las acciones de botón (incluyendo `confirmar_accion`) llegan
  automáticamente al mismo `onSend` del `A2uiTransportAdapter` — no hay
  que suscribirse a nada aparte. `Conversation` internamente hace
  `controller.onSubmit.listen(sendRequest)`, y `SurfaceController`
  empuja ahí un `ChatMessage.user('', parts: [UiInteractionPart.create(
  jsonEncode({'version': 'v0.9', 'action': event.toMap()}))])` cada vez
  que se toca un botón en cualquier superficie.
- `Surface` requiere `surfaceContext` (obtenido con
  `SurfaceController.contextFor(surfaceId)`), no `host`/`surfaceId`.
- El parseo de JSON a `A2uiMessage` usa el factory
  `A2uiMessage.fromJson(Map<String, dynamic>)` de `package:a2ui_core`
  — que hay que agregar explícitamente a `pubspec.yaml` (hoy solo es
  dependencia transitiva de `genui`, y Dart exige declarar
  explícitamente lo que se importa directamente).

**Queda un solo detalle sin confirmar por la Task 1** (marcado abajo
como "AJUSTAR AQUÍ"): el nombre exacto del campo dentro de
`UiInteractionPart` que expone el JSON crudo que se le pasó a
`.create(...)`. Verificarlo con:

```bash
grep -n "class UiInteractionPart" -A 20 ~/.pub-cache/hosted/pub.dev/genui-0.10.3/lib/src/model/*.dart
```

- [ ] **Step 1: Agregar `a2ui_core` a `pubspec.yaml`**

En `flutter_app/pubspec.yaml`, agregar bajo `dependencies:` (junto a
`genui`, `http`, `shared_preferences` ya agregados en la Task 1):

```yaml
  a2ui_core: ^0.1.1
```

Luego: `cd flutter_app && flutter pub get`.

- [ ] **Step 2: Implementar `lib/chat/chat_screen.dart`**

```dart
// flutter_app/lib/chat/chat_screen.dart
import 'dart:convert';

import 'package:a2ui_core/a2ui_core.dart';
import 'package:flutter/material.dart';
import 'package:genui/genui.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import 'action_router.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final ApiClient apiClient;
  final AuthController authController;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

// Un turno de la transcripción: o bien un mensaje del usuario (texto
// plano), o bien la superficie A2UI que armó el agente para ese turno.
// Mismo patrón de "cada turno es una entrada nueva" que ya aplicamos
// en React — nunca se sobrescribe un turno anterior.
sealed class ChatTurn {
  const ChatTurn(this.id);
  final String id;
}

class UserTurn extends ChatTurn {
  UserTurn(super.id, this.text);
  final String text;
}

class AgentTurn extends ChatTurn {
  AgentTurn(super.id, this.surfaceId);
  final String surfaceId;
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  final List<ChatTurn> _turns = [];
  bool _sending = false;
  String? _errorMessage;
  int _turnCounter = 0;

  late final SurfaceController _surfaceController;
  late final A2uiTransportAdapter _transport;
  late final Conversation _conversation;

  @override
  void initState() {
    super.initState();

    _surfaceController = SurfaceController(
      catalogs: [CoreCatalogItems.asCatalog()],
    );

    _transport = A2uiTransportAdapter(onSend: _handleSend);

    _conversation = Conversation(
      controller: _surfaceController,
      transport: _transport,
    );

    _conversation.events.listen((event) {
      if (event is ConversationSurfaceAdded) {
        setState(() {
          _turns.add(AgentTurn('turn-${_turnCounter++}', event.surfaceId));
        });
      }
    });
  }

  late final ActionRouter _actionRouter = ActionRouter(
    confirmAction: (proposalId) =>
        widget.apiClient.confirmAction(widget.authController.token!, proposalId),
    onMessages: _feedMessagesToConversation,
    onError: (err) => _handleError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
  );

  void _feedMessagesToConversation(List<dynamic> messages) {
    for (final message in messages) {
      _transport.addMessage(A2uiMessage.fromJson(message as Map<String, dynamic>));
    }
  }

  Future<void> _handleSend(ChatMessage message) async {
    // Cualquier acción de botón (incluyendo confirmar_accion) llega aquí
    // automáticamente: Conversation suscribe internamente
    // controller.onSubmit.listen(sendRequest), y sendRequest reenvía al
    // onSend del transporte el ChatMessage que armó
    // SurfaceController.handleUiEvent (ver GENUI_API_NOTES.md). Los
    // mensajes de texto del usuario NO pasan por aquí — ver
    // _handleSubmit abajo, que llama a la API propia directamente sin
    // pasar por _conversation.sendRequest.
    final interactionPart = message.parts.whereType<UiInteractionPart>().firstOrNull;
    if (interactionPart == null) {
      return;
    }
    // AJUSTAR AQUÍ si el campo real de UiInteractionPart con el JSON
    // crudo no se llama `.data` — ver el grep sugerido arriba, antes
    // del Step 1 de esta tarea.
    final decoded = jsonDecode(interactionPart.data) as Map<String, dynamic>;
    final action = decoded['action'] as Map<String, dynamic>;
    await _actionRouter.handle(action);
  }

  void _handleError(Object err, String fallback) {
    if (err is ApiException && err.statusCode == 401) {
      widget.authController.logout();
      return;
    }
    setState(() {
      _errorMessage = err is ApiException ? (err.detail ?? fallback) : fallback;
    });
  }

  Future<void> _handleSubmit() async {
    final texto = _messageController.text.trim();
    if (texto.isEmpty || _sending) {
      return;
    }
    setState(() {
      _sending = true;
      _errorMessage = null;
      _turns.add(UserTurn('turn-${_turnCounter++}', texto));
    });
    _messageController.clear();
    try {
      final token = widget.authController.token!;
      final messages = await widget.apiClient.sendMessage(token, texto);
      _feedMessagesToConversation(messages);
    } catch (err) {
      _handleError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _transport.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('me-alcanza'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: widget.authController.logout,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _turns.isEmpty
                ? const Center(child: Text('Escribe tu primer mensaje para empezar.'))
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _turns.length,
                    itemBuilder: (context, index) {
                      final turn = _turns[index];
                      if (turn is UserTurn) {
                        return Align(
                          alignment: Alignment.centerRight,
                          child: Container(
                            margin: const EdgeInsets.symmetric(vertical: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.primary,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              turn.text,
                              style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
                            ),
                          ),
                        );
                      }
                      turn as AgentTurn;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Surface(
                          surfaceContext: _surfaceController.contextFor(turn.surfaceId),
                        ),
                      );
                    },
                  ),
          ),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _messageController,
                      enabled: !_sending,
                      decoration: const InputDecoration(hintText: 'Escribe tu mensaje...'),
                      onSubmitted: (_) => _handleSubmit(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _sending ? null : _handleSubmit,
                    child: Text(_sending ? 'Enviando...' : 'Enviar'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 3: Resolver el único detalle marcado "AJUSTAR AQUÍ"**

Correr el `grep` sugerido arriba (antes del Step 1) para confirmar el
nombre real del campo de `UiInteractionPart` que expone el JSON crudo.
Si no es `.data`, corregir esa línea en `_handleSend`. Si `UiInteractionPart`
no tiene un campo público directo (ej. si el JSON solo es accesible vía
algún método), usar lo que el código fuente real muestre.

- [ ] **Step 4: Verificar que compila**

Run: `cd flutter_app && flutter analyze`
Expected: sin errores. Si algún símbolo (`Surface`, `A2uiMessage`,
`UiInteractionPart`, `ConversationSurfaceAdded`, etc.) no existe con el
nombre exacto usado arriba, corregirlo releyendo
`flutter_app/GENUI_API_NOTES.md` y, si hace falta, el código fuente real
del paquete (rutas documentadas ahí).

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/chat/chat_screen.dart flutter_app/pubspec.yaml flutter_app/pubspec.lock
git commit -m "feat: add ChatScreen with genui surface rendering and action wiring"
```

---

### Task 7: `AppShell` — navegación de 3 tabs + `main.dart`

**Files:**
- Create: `flutter_app/lib/shell/app_shell.dart`
- Create: `flutter_app/lib/dashboard/dashboard_placeholder_screen.dart`
- Create: `flutter_app/lib/yo/yo_placeholder_screen.dart`
- Modify: `flutter_app/lib/main.dart` (overwrite entero)
- Create: `flutter_app/lib/config.dart`

**Interfaces:**
- Consumes: `AuthController`/`LoginScreen` (Task 5), `ChatScreen` (Task 6), `ApiClient` (Task 2).
- Produces: la app montada — el entregable que verifica manualmente la Task 9.

- [ ] **Step 1: Crear `lib/config.dart` (URL base del backend)**

```dart
// flutter_app/lib/config.dart

// El emulador Android usa 10.0.2.2 para referirse a localhost de la
// máquina host — NUNCA localhost directo (eso apuntaría al propio
// dispositivo virtual). Si se prueba en un celular físico en la misma
// red Wi-Fi que la laptop, cambiar esto a la IP de red local de la
// laptop (ej. 192.168.1.50) — ver flutter_app/README.md.
const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);
```

- [ ] **Step 2: Crear los placeholders**

```dart
// flutter_app/lib/dashboard/dashboard_placeholder_screen.dart
import 'package:flutter/material.dart';

class DashboardPlaceholderScreen extends StatelessWidget {
  const DashboardPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: const Center(child: Text('Próximamente')),
    );
  }
}
```

```dart
// flutter_app/lib/yo/yo_placeholder_screen.dart
import 'package:flutter/material.dart';

class YoPlaceholderScreen extends StatelessWidget {
  const YoPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Yo')),
      body: const Center(child: Text('Próximamente')),
    );
  }
}
```

- [ ] **Step 3: Implementar `lib/shell/app_shell.dart`**

```dart
// flutter_app/lib/shell/app_shell.dart
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import '../chat/chat_screen.dart';
import '../dashboard/dashboard_placeholder_screen.dart';
import '../login/login_screen.dart';
import '../yo/yo_placeholder_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final ApiClient apiClient;
  final AuthController authController;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _currentIndex = 1; // Chat es el tab inicial.

  @override
  void initState() {
    super.initState();
    widget.authController.addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    widget.authController.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() => setState(() {});

  @override
  Widget build(BuildContext context) {
    if (widget.authController.token == null) {
      return LoginScreen(authController: widget.authController);
    }

    final screens = [
      const DashboardPlaceholderScreen(),
      ChatScreen(apiClient: widget.apiClient, authController: widget.authController),
      const YoPlaceholderScreen(),
    ];

    return Scaffold(
      body: screens[_currentIndex],
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

- [ ] **Step 4: Overwrite `lib/main.dart`**

```dart
// flutter_app/lib/main.dart
import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'auth/auth_controller.dart';
import 'auth/auth_repository.dart';
import 'config.dart';
import 'shell/app_shell.dart';

void main() {
  runApp(const MeAlcanzaApp());
}

class MeAlcanzaApp extends StatefulWidget {
  const MeAlcanzaApp({super.key});

  @override
  State<MeAlcanzaApp> createState() => _MeAlcanzaAppState();
}

class _MeAlcanzaAppState extends State<MeAlcanzaApp> {
  late final ApiClient _apiClient = ApiClient(apiBaseUrl);
  late final AuthController _authController = AuthController(
    apiClient: _apiClient,
    authRepository: AuthRepository(),
  );

  @override
  void initState() {
    super.initState();
    _authController.restoreSession();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'me-alcanza',
      theme: ThemeData(useMaterial3: true),
      home: ListenableBuilder(
        listenable: _authController,
        builder: (context, _) => AppShell(
          apiClient: _apiClient,
          authController: _authController,
        ),
      ),
    );
  }
}
```

- [ ] **Step 5: Verificar que compila**

Run: `cd flutter_app && flutter analyze`
Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/shell/app_shell.dart flutter_app/lib/dashboard/dashboard_placeholder_screen.dart flutter_app/lib/yo/yo_placeholder_screen.dart flutter_app/lib/main.dart flutter_app/lib/config.dart
git commit -m "feat: wire AppShell with 3-tab navigation and placeholders"
```

---

### Task 8: Tema visual — paleta Banorte

**Files:**
- Modify: `flutter_app/lib/main.dart`

**Interfaces:**
- Consumes: la paleta documentada en `docs/design-system.md`.
- Produces: `ThemeData` aplicado globalmente vía `MaterialApp`.

- [ ] **Step 1: Reemplazar `theme: ThemeData(useMaterial3: true)` en `lib/main.dart`**

```dart
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFEC0029),
          primary: const Color(0xFFEC0029),
          onPrimary: Colors.white,
          secondary: const Color(0xFF6A6867),
          onSecondary: Colors.white,
          surface: Colors.white,
          onSurface: const Color(0xFF1F1F1F),
          error: const Color(0xFFC5221F),
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F5F5),
      ),
```

- [ ] **Step 2: Verificar que compila**

Run: `cd flutter_app && flutter analyze`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/main.dart
git commit -m "style: apply Banorte color palette to Flutter theme"
```

---

### Task 9: README + verificación manual completa

**Files:**
- Create: `flutter_app/README.md`

**Interfaces:**
- Consumes: la app completa de las Tasks 1-8, más el backend ya implementado.

- [ ] **Step 1: Crear `flutter_app/README.md`**

```markdown
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
```

- [ ] **Step 2: Correr toda la suite de tests**

Run: `cd flutter_app && flutter test`
Expected: PASS — 12 tests (5 `api_client_test.dart` + 3
`auth_repository_test.dart` + 4 `action_router_test.dart`).

- [ ] **Step 3: Verificar que la app compila para Android**

Run: `cd flutter_app && flutter build apk --debug`
Expected: PASS — genera un APK sin errores. Esto compila el código
real para Android sin necesitar un emulador corriendo, y es la
verificación automatizable más fuerte disponible en este entorno de
desarrollo (que no tiene un emulador Android configurado — ver
`flutter doctor`).

- [ ] **Step 4: Verificación manual end-to-end (requiere un emulador/dispositivo del equipo)**

Si el entorno donde se ejecuta este plan no tiene un emulador Android
configurado (`flutter doctor` marcando "Android licenses not
accepted" o sin ningún dispositivo en `flutter devices`), esta
verificación queda pendiente para que el equipo la corra en su propia
máquina/dispositivo antes de la demo — documentarlo explícitamente en
el reporte de esta tarea, no fingir que se hizo.

Si sí hay un emulador/dispositivo disponible: levantar el backend real
(`uv run me-alcanza` desde la raíz del repo, con `.env` configurado) y
correr `flutter run` en `flutter_app/`, siguiendo los dos flujos del
README arriba.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/README.md
git commit -m "docs: add Flutter frontend README with setup and manual verification steps"
```

---

## Qué sigue

Con este plan, `me-alcanza` tiene sus cuatro entregables planeados
(MCP server, backend, React, Flutter) integrados contra el mismo
backend sin duplicar lógica de negocio. Pendiente fuera de este plan:
funcionalidad real en Dashboard/Yo (hoy placeholders, por decisión
explícita), y la verificación manual en un emulador/dispositivo real si
este entorno de desarrollo no tuviera uno configurado.
