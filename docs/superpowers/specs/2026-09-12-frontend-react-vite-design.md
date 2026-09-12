# Diseño: frontend React (Vite) para me-alcanza

## Objetivo

Construir el cliente React (`frontend/`) que consume el backend FastAPI ya
implementado (`POST /api/login`, `POST /api/chat`, `POST /api/confirm-action`)
y renderiza las superficies A2UI que arma el agente, para los dos flujos
núcleo del reto: "¿me alcanza para X?" (+ apartado de ahorro) y transferencia
con desambiguación. Es la ruta crítica de la demo de HackMTY 2026; un
frontend Flutter secundario se documenta como placeholder para después, no
se construye en este spec.

Referencia: `docs/superpowers/specs/2026-09-11-me-alcanza-design.md` (diseño
general del sistema, ya implementado en `src/me_alcanza/backend/`).

## Alcance

**Incluido:**

1. App Vite + React + **JavaScript** (sin TypeScript) en `frontend/`.
2. Pantalla de login (usuario/password demo hardcodeados en el backend) que
   guarda el JWT y lo persiste en `localStorage` (sobrevive a un refresh de
   página; se limpia en logout o en un 401).
3. Pantalla de chat: input de texto libre + render de las superficies A2UI
   que arma el agente (`@a2ui/react` + `@a2ui/web_core`, protocolo v0_9,
   `basicCatalog`), con `surfaceId` fijo (`"main"`, ya lo fija el backend) y
   actualización incremental (`updateComponents`) entre turnos.
4. Manejador global de acciones A2UI que traduce el evento
   `confirmar_accion` (con `context.proposalId`) emitido por cualquier botón
   de confirmación en `POST /api/confirm-action`, y reinyecta la respuesta al
   mismo processor.
5. Manejo de errores de red/HTTP acorde a los códigos que ya define el
   backend (401, 409, 503/500).
6. Pase de diseño visual ligero (skill `frontend-design`) para el login, el
   header y el input de chat — las tarjetas que arma el LLM usan el estilo
   por defecto de `basicCatalog`.
7. Configuración vía `VITE_API_BASE_URL` (`.env` de frontend, no versionado).

**Excluido (fuera de alcance para este spec):**

- Cualquier scaffolding de Flutter (`frontend_flutter/`) — solo se documenta
  como nota de compatibilidad de contrato (ver sección "Flutter (futuro)").
- Suite de pruebas automatizadas de UI (E2E, componentes) — verificación
  manual en navegador, igual que ya decidido en el spec general.
- Streaming/SSE incremental — el backend responde un JSON completo por
  turno.
- Router / múltiples rutas — son 2 pantallas, alternadas por estado de
  autenticación, no por URL.
- Registro de usuario, recuperación de contraseña, refresh tokens — no
  existen en el backend.
- Componentes A2UI custom — solo `basicCatalog`.

## Arquitectura

```
┌─────────────────────────────┐
│ frontend/ (Vite + React JS)  │
│                              │
│  AuthContext ──────────────┐│
│    (token en localStorage) ││
│                             ▼│
│  LoginView  ──login──▶ ChatView
│                             │ │
│                             │ ├─ MessageProcessor([basicCatalog], actionHandler)
│                             │ │     (una instancia por sesión de chat)
│                             │ ├─ <A2uiSurface> por cada surface del processor
│                             │ └─ input de texto libre
│                             │
│                    api/client.js
│         (fetch + Authorization: Bearer <token>)
└──────────────┬───────────────┘
               │ POST /api/login, /api/chat, /api/confirm-action
               ▼
   Backend FastAPI (ya implementado, src/me_alcanza/backend/)
```

El frontend no mantiene copia propia de saldos/estado bancario ni de la
conversación: toda la "memoria" de negocio vive en el backend (por
`account_id`, vía JWT). El único estado que el frontend posee es de UI:
token de sesión, y el árbol de componentes/datos que mantiene el
`MessageProcessor` de A2UI en memoria del navegador (se pierde al recargar,
igual que la conversación en el backend — ambos son efímeros, aceptable
para la demo).

## Componentes

### `src/api/client.js`

Módulo delgado sobre `fetch`, sin dependencias extra:

- `login(username, password) -> {token}` → `POST /api/login`.
- `sendMessage(mensaje) -> {a2ui_messages}` → `POST /api/chat` con header
  `Authorization: Bearer <token>`.
- `confirmAction(proposalId) -> {a2ui_messages}` → `POST /api/confirm-action`
  con el mismo header.
- Cada función parsea el `detail` de error del backend cuando el status no
  es 2xx y lanza un error tipado (`{status, detail}`) para que la UI decida
  qué mostrar. Un 401 en cualquier llamada (excepto `login`) dispara un
  callback `onUnauthorized` (inyectado desde `AuthContext`) que limpia la
  sesión.

### `src/auth/AuthContext.jsx`

- Contexto de React con `{ token, login(user, pass), logout() }`.
- Al montar la app, lee el token de `localStorage`; si existe, se asume
  sesión activa (no hay endpoint de "whoami"/refresh — un token expirado
  simplemente hará fallar la primera llamada a `/chat` con 401, que dispara
  `logout()` y vuelve a Login).
- `login()` llama a `api/client.js#login`, guarda el token en estado +
  `localStorage`.
- `logout()` limpia ambos.

### `src/views/LoginView.jsx`

- Formulario controlado (usuario, password), botón "Entrar".
- Muestra el `detail` del error si el login falla (401/503).
- Sin registro ni recuperación de contraseña (no existen en el backend).

### `src/views/ChatView.jsx`

- Crea (memoizado con `useState(() => ...)`, una sola vez por sesión de
  chat) el `MessageProcessor` de `@a2ui/web_core/v0_9` con `[basicCatalog]`
  y el `actionHandler` descrito abajo.
- Llama `injectStyles()` de `@a2ui/react/styles` una vez al montar (limpieza
  con `removeStyles()` al desmontar).
- Se suscribe a `onSurfaceCreated`/`onSurfaceDeleted` del processor (patrón
  del quickstart oficial de `@a2ui/react`) y renderiza un `<A2uiSurface>`
  por cada surface activa — en la práctica siempre una sola, `"main"`.
- Input de texto libre + botón enviar: en submit, llama
  `api/client.js#sendMessage`, y alimenta `a2ui_messages` de la respuesta a
  `processor.processMessages(...)`.
- Mientras espera respuesta de `/chat` o `/confirm-action`, deshabilita el
  input y muestra un indicador simple de "pensando" (no bloquea el render
  de la superficie existente).

### `actionHandler` (función pasada al `MessageProcessor`)

Es la pieza que conecta el árbol de UI generado por el LLM con el backend.
Contrato ya fijado por el system prompt del backend
(`orchestrator.py::build_system_prompt`): un botón de confirmación siempre
dispara la acción `confirmar_accion` con `context = {proposalId: "<id>"}`.

```js
async function actionHandler(action) {
  if (action.name !== 'confirmar_accion') {
    return; // ninguna otra acción está definida en el contrato actual
  }
  const proposalId = action.context?.proposalId;
  try {
    const { a2ui_messages } = await confirmAction(proposalId);
    processor.processMessages(a2ui_messages);
  } catch (err) {
    // 409 (expirada/inválida) ya trae su propio bloque A2UI de error desde
    // el backend en algunos casos; para errores de red/500 se muestra un
    // bloque de error local mínimo con el mismo processor.
  }
}
```

No hay otro tipo de acción en el contrato hoy (la desambiguación de
contactos se resuelve con tarjetas de confirmación paralelas, una por
candidato — ver spec general —, no con una acción de selección separada).

## Flujo de datos

1. Usuario abre la app → `AuthContext` intenta leer token de `localStorage`.
   Sin token → `LoginView`.
2. Login exitoso → token en estado + `localStorage` → `ChatView`.
3. `ChatView` monta el `MessageProcessor`; aún no hay superficie hasta el
   primer mensaje (el backend crea `"main"` en la primera respuesta de
   `/chat`).
4. Usuario escribe y envía → `POST /api/chat` → respuesta
   `{a2ui_messages}` → `processor.processMessages(...)` → la superficie
   `"main"` se crea/actualiza → React re-renderiza.
5. Si la respuesta incluye una tarjeta con botón de confirmación, el click
   dispara `confirmar_accion` → `actionHandler` → `POST /api/confirm-action`
   → nueva tanda de `a2ui_messages` (confirmación o error) → mismo processor
   → mismo `surfaceId`, `updateComponents` incremental.
6. Cualquier 401 en el camino → `logout()` → vuelve a `LoginView`.

## Manejo de errores

- **401** (token ausente/inválido/expirado, en `/chat` o `/confirm-action`):
  `AuthContext.logout()`, redirige a `LoginView`; no se reintenta la
  petición automáticamente.
- **401** en `/login` (credenciales incorrectas): se muestra el `detail` del
  backend en el propio formulario, sin tocar la sesión.
- **503** en `/login` (MCP caído) y **500/503** en `/chat` o
  `/confirm-action`: mensaje de error visible en la UI (banner o bloque A2UI
  local mínimo), la superficie existente no se destruye.
- **409** en `/confirm-action` (propuesta expirada, no encontrada, o de otra
  cuenta): el backend ya responde con su propio bloque A2UI explicando que
  hay que pedir la acción de nuevo; el frontend solo lo renderiza como
  cualquier otra respuesta.
- Error de red (backend no alcanzable): mensaje genérico + el input de chat
  se vuelve a habilitar para reintentar.

## Testing

Igual que ya decidido en el spec general: no se justifica una suite
automatizada de UI para una demo de un día. Verificación manual en
navegador (`npm run dev`) de los dos flujos completos:

1. Login → "¿me alcanza para el concierto del 13 de octubre?" → veredicto →
   (si no alcanza) confirmar apartado → ver bloque de confirmación.
2. Login → "deposítale 500 a mi hermano Pepe" → dos tarjetas de
   confirmación (desambiguación) → confirmar la correcta → ver bloque de
   confirmación.

## Configuración

`frontend/.env` (no versionado, análogo al `.env` del backend):

```
VITE_API_BASE_URL=http://localhost:8000
```

## Dependencias

- `vite`, `react`, `react-dom` (JavaScript, sin plugin de TypeScript).
- `@a2ui/react` (`^0.11.1`), `@a2ui/web_core` (`^0.11.0`) — ya verificadas
  como paquetes reales publicados en npm por el equipo de A2UI (Google).
- Sin librería de routing ni de manejo de estado adicional (Context API +
  `useState`/`useEffect` alcanzan para 2 pantallas y un processor).
- Sin librería de estilos (CSS plano + variables `:root` para el pase de
  diseño ligero).

## Flutter (futuro, fuera de este spec)

El spec general ya documenta un segundo frontend (`frontend_flutter/`, con
`genui` + `genui_a2ui`) como cliente secundario del mismo backend. El
contrato que este spec fija (`surfaceId="main"`, acción `confirmar_accion`
con `context.proposalId`) es agnóstico de framework — Flutter consumirá los
mismos endpoints y el mismo protocolo A2UI sin que el backend ni el
contrato cambien. No se crea ningún scaffolding de Flutter en este spec; es
una nota de compatibilidad para cuando se aborde como su propio
spec/plan.

## Fuera de este spec (posible follow-up)

- Frontend Flutter (spec y plan propios).
- Suite de pruebas E2E (ej. Playwright) si el proyecto crece más allá de la
  demo.
- Manejo de expiración de token con aviso proactivo (hoy se descubre en la
  siguiente llamada fallida).
