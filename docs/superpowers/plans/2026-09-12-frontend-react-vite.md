# Frontend React (Vite, JavaScript) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `frontend/` React client that logs in against the existing FastAPI backend, sends chat messages, renders the A2UI surfaces the agent generates, and confirms proposed actions (apartado/transferencia) through `POST /api/confirm-action`.

**Architecture:** A 2-screen Vite + React (plain JavaScript) SPA with no router. `AuthContext` holds the JWT (persisted in `localStorage`) and switches between `LoginView` and `ChatView`. `ChatView` owns one `@a2ui/web_core` `MessageProcessor` for the session, rendering every surface it tracks with `@a2ui/react`'s `A2uiSurface` + `basicCatalog`. A single global action handler intercepts the `confirmar_accion` event (the only action the backend's system prompt ever emits) and calls `/api/confirm-action`, feeding the response back into the same processor.

**Tech Stack:** Vite 8, React 19 (JavaScript, no TypeScript), `@a2ui/react` `^0.11.1`, `@a2ui/web_core` `^0.11.0`, Vitest 5 for unit tests of plain-JS modules (no automated UI/component tests).

**Spec:** `docs/superpowers/specs/2026-09-12-frontend-react-vite-design.md`

## Global Constraints

- JavaScript only — no TypeScript, no `.ts`/`.tsx` files, no `@types/*` packages.
- Package manager: `npm` (no `pnpm`/`yarn` available in this environment).
- No third-party router — 2 screens (`LoginView`/`ChatView`) switched by auth state, not by URL.
- No state-management library beyond React's Context API + hooks.
- No automated UI/E2E test suite — React components (`LoginView`, `ChatView`, `App`) are verified manually against the running backend. Plain-JS modules (`api/client.js`, `auth/tokenStorage.js`, `chat/actionHandler.js`) get Vitest unit tests.
- `surfaceId` is always `"main"` — this is fixed server-side (`orchestrator.py`), the frontend never sets it.
- The only action name the backend ever emits is `confirmar_accion`, always with `context.proposalId` set to the id returned by `proponer_apartado`/`proponer_transferencia`. No other action name exists in the contract.
- `VITE_API_BASE_URL` (default `http://localhost:8000`) configures the backend base URL; never hardcode the URL outside of this env var's fallback.
- No Flutter scaffolding of any kind in this plan.

---

## Task 1: Scaffold the Vite + React (JS) project

**Files:**
- Create: `frontend/` (via `npm create vite@latest`, template `react`)
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.js`
- Create: `frontend/.env.example`
- Delete: `frontend/src/App.css`, `frontend/src/assets/hero.png`, `frontend/src/assets/react.svg`, `frontend/src/assets/vite.svg`, `frontend/.oxlintrc.json`

**Interfaces:**
- Produces: a working `npm run build`, `npm run dev`, and `npm test` (Vitest) in `frontend/`, which every later task relies on.

- [ ] **Step 1: Scaffold with create-vite**

Run from the repo root:

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

- [ ] **Step 2: Remove template boilerplate not used by this app**

```bash
rm -f frontend/src/App.css
rm -rf frontend/src/assets
rm -f frontend/.oxlintrc.json
```

- [ ] **Step 3: Trim `frontend/package.json` to what this project actually uses**

Replace its contents with:

```json
{
  "name": "me-alcanza-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@a2ui/react": "^0.11.1",
    "@a2ui/web_core": "^0.11.0",
    "react": "^19.2.8",
    "react-dom": "^19.2.8"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^6.1.1",
    "vite": "^8.3.0",
    "vitest": "^5.0.0"
  }
}
```

Then run:

```bash
cd frontend
npm install
```

- [ ] **Step 4: Add the Vitest config to `frontend/vite.config.js`**

Replace its contents with:

```js
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
  },
})
```

- [ ] **Step 5: Create `frontend/.env.example`**

```
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 6: Verify the scaffold builds**

Run: `cd frontend && npm run build`
Expected: build succeeds, prints a `dist/` output summary, no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/ 
git commit -m "chore: scaffold Vite + React (JS) frontend"
```

---

## Task 2: `api/client.js` — thin fetch wrapper for the backend

**Files:**
- Create: `frontend/src/api/client.js`
- Test: `frontend/src/api/client.test.js`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure module, only depends on global `fetch`).
- Produces:
  - `class ApiError extends Error` with fields `status: number`, `detail: string | undefined`.
  - `function createApiClient(baseUrl: string) -> { login(username, password), sendMessage(token, mensaje), confirmAction(token, proposalId) }` — each method returns a `Promise` resolving to the parsed JSON body, or rejecting with an `ApiError`.
  - `const apiClient` — a singleton created with `import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'`, for use by the rest of the app.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/api/client.test.js`:

```js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createApiClient, ApiError } from './client.js';

describe('createApiClient', () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock;
  });

  it('posts credentials to /api/login and returns the token', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ token: 'jwt-123' }),
    });
    const client = createApiClient('http://api.test');

    const result = await client.login('ana', 'pass123');

    expect(result).toEqual({ token: 'jwt-123' });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/login',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'ana', password: 'pass123' }),
      }),
    );
  });

  it('sends the bearer token and mensaje on /api/chat', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [] }),
    });
    const client = createApiClient('http://api.test');

    await client.sendMessage('jwt-123', '¿me alcanza para el concierto?');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/chat',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
        body: JSON.stringify({ mensaje: '¿me alcanza para el concierto?' }),
      }),
    );
  });

  it('sends proposal_id on /api/confirm-action', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [] }),
    });
    const client = createApiClient('http://api.test');

    await client.confirmAction('jwt-123', 'prop-1');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/confirm-action',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
        body: JSON.stringify({ proposal_id: 'prop-1' }),
      }),
    );
  });

  it('throws an ApiError carrying the backend detail on a non-2xx response', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Usuario o contraseña incorrectos' }),
    });
    const client = createApiClient('http://api.test');

    await expect(client.login('ana', 'wrong')).rejects.toMatchObject({
      status: 401,
      detail: 'Usuario o contraseña incorrectos',
    });
  });

  it('falls back to a status-only ApiError when the error body is not JSON', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json');
      },
    });
    const client = createApiClient('http://api.test');

    await expect(client.login('ana', 'x')).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/api/client.test.js`
Expected: FAIL — `Cannot find module './client.js'` (or similar), since `client.js` doesn't exist yet.

- [ ] **Step 3: Implement `frontend/src/api/client.js`**

```js
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Error HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(response) {
  try {
    const body = await response.json();
    return body.detail;
  } catch {
    return undefined;
  }
}

export function createApiClient(baseUrl) {
  async function post(path, { token, body } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body ?? {}),
    });
    if (!response.ok) {
      throw new ApiError(response.status, await parseErrorDetail(response));
    }
    return response.json();
  }

  return {
    login: (username, password) => post('/api/login', { body: { username, password } }),
    sendMessage: (token, mensaje) => post('/api/chat', { token, body: { mensaje } }),
    confirmAction: (token, proposalId) =>
      post('/api/confirm-action', { token, body: { proposal_id: proposalId } }),
  };
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient = createApiClient(DEFAULT_BASE_URL);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/api/client.test.js`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.js frontend/src/api/client.test.js
git commit -m "feat: add api client for login/chat/confirm-action"
```

---

## Task 3: `auth/tokenStorage.js` — persist the JWT across reloads

**Files:**
- Create: `frontend/src/auth/tokenStorage.js`
- Test: `frontend/src/auth/tokenStorage.test.js`

**Interfaces:**
- Consumes: nothing (pure module using `globalThis.localStorage`).
- Produces: `readStoredToken() -> string | null`, `writeStoredToken(token: string) -> void`, `clearStoredToken() -> void`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/auth/tokenStorage.test.js`:

```js
import { describe, it, expect, beforeEach } from 'vitest';
import { readStoredToken, writeStoredToken, clearStoredToken } from './tokenStorage.js';

function createFakeStorage() {
  const store = new Map();
  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key),
  };
}

describe('tokenStorage', () => {
  beforeEach(() => {
    globalThis.localStorage = createFakeStorage();
  });

  it('returns null when nothing is stored', () => {
    expect(readStoredToken()).toBeNull();
  });

  it('round-trips a token through write/read', () => {
    writeStoredToken('jwt-abc');
    expect(readStoredToken()).toBe('jwt-abc');
  });

  it('clears a stored token', () => {
    writeStoredToken('jwt-abc');
    clearStoredToken();
    expect(readStoredToken()).toBeNull();
  });

  it('does not throw when localStorage is unavailable', () => {
    globalThis.localStorage = undefined;
    expect(() => writeStoredToken('jwt-abc')).not.toThrow();
    expect(readStoredToken()).toBeNull();
    expect(() => clearStoredToken()).not.toThrow();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/auth/tokenStorage.test.js`
Expected: FAIL — `Cannot find module './tokenStorage.js'`.

- [ ] **Step 3: Implement `frontend/src/auth/tokenStorage.js`**

```js
const STORAGE_KEY = 'me_alcanza_token';

export function readStoredToken() {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

export function writeStoredToken(token) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, token);
  } catch {
    // localStorage no disponible (modo privado, cuota, etc.) — la sesión
    // sigue funcionando en memoria durante la vida de la pestaña.
  }
}

export function clearStoredToken() {
  try {
    globalThis.localStorage?.removeItem(STORAGE_KEY);
  } catch {
    // no-op
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/auth/tokenStorage.test.js`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/auth/tokenStorage.js frontend/src/auth/tokenStorage.test.js
git commit -m "feat: add localStorage-backed token persistence"
```

---

## Task 4: `chat/actionHandler.js` — routes the `confirmar_accion` event

**Files:**
- Create: `frontend/src/chat/actionHandler.js`
- Test: `frontend/src/chat/actionHandler.test.js`

**Interfaces:**
- Consumes: nothing directly (pure factory function; the caller supplies `confirmAction`/`onMessages`/`onError` callbacks matching `api/client.js`'s `confirmAction(token, proposalId)` shape, wired up in Task 6).
- Produces: `const CONFIRM_ACTION_NAME = 'confirmar_accion'` and
  `createActionHandler({ confirmAction: (proposalId) => Promise<{a2ui_messages}>, onMessages: (a2ui_messages) => void, onError: (err) => void }) -> (action: {name, context, surfaceId, sourceComponentId, timestamp}) => Promise<void>` — this returned function is what Task 6 passes as the `actionHandler` to `MessageProcessor`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/chat/actionHandler.test.js`:

```js
import { describe, it, expect, vi } from 'vitest';
import { createActionHandler, CONFIRM_ACTION_NAME } from './actionHandler.js';

function makeAction(overrides = {}) {
  return {
    name: CONFIRM_ACTION_NAME,
    context: { proposalId: 'prop-1' },
    surfaceId: 'main',
    sourceComponentId: 'btn-1',
    timestamp: '2026-09-12T00:00:00Z',
    ...overrides,
  };
}

describe('createActionHandler', () => {
  it('ignores actions with a name other than confirmar_accion', async () => {
    const confirmAction = vi.fn();
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ confirmAction, onMessages, onError });

    await handleAction(makeAction({ name: 'otra_accion' }));

    expect(confirmAction).not.toHaveBeenCalled();
    expect(onMessages).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('confirms the proposal from context.proposalId and forwards the resulting messages', async () => {
    const confirmAction = vi.fn().mockResolvedValue({ a2ui_messages: [{ foo: 'bar' }] });
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ confirmAction, onMessages, onError });

    await handleAction(makeAction());

    expect(confirmAction).toHaveBeenCalledWith('prop-1');
    expect(onMessages).toHaveBeenCalledWith([{ foo: 'bar' }]);
    expect(onError).not.toHaveBeenCalled();
  });

  it('reports an error when confirming the proposal fails, without touching onMessages', async () => {
    const failure = new Error('boom');
    const confirmAction = vi.fn().mockRejectedValue(failure);
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ confirmAction, onMessages, onError });

    await handleAction(makeAction());

    expect(onError).toHaveBeenCalledWith(failure);
    expect(onMessages).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/chat/actionHandler.test.js`
Expected: FAIL — `Cannot find module './actionHandler.js'`.

- [ ] **Step 3: Implement `frontend/src/chat/actionHandler.js`**

```js
export const CONFIRM_ACTION_NAME = 'confirmar_accion';

export function createActionHandler({ confirmAction, onMessages, onError }) {
  return async function handleAction(action) {
    if (action.name !== CONFIRM_ACTION_NAME) {
      return;
    }
    const proposalId = action.context?.proposalId;
    try {
      const { a2ui_messages } = await confirmAction(proposalId);
      onMessages(a2ui_messages);
    } catch (err) {
      onError(err);
    }
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- src/chat/actionHandler.test.js`
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/chat/actionHandler.js frontend/src/chat/actionHandler.test.js
git commit -m "feat: add confirmar_accion action router"
```

---

## Task 5: `AuthContext` + `LoginView`

**Files:**
- Create: `frontend/src/auth/AuthContext.jsx`
- Create: `frontend/src/views/LoginView.jsx`

**Interfaces:**
- Consumes: `apiClient` from `frontend/src/api/client.js` (Task 2), `readStoredToken`/`writeStoredToken`/`clearStoredToken` from `frontend/src/auth/tokenStorage.js` (Task 3).
- Produces: `<AuthProvider>` (wraps the app), `useAuth() -> { token: string | null, login(username, password): Promise<void>, logout(): void }` — consumed by `App.jsx` (Task 7) and `ChatView.jsx` (Task 6). `LoginView` default export — a component rendered by `App.jsx` when `token` is `null`.

No automated tests for this task (React components — see Global Constraints); verified manually in Step 4.

- [ ] **Step 1: Implement `frontend/src/auth/AuthContext.jsx`**

```jsx
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { apiClient } from '../api/client.js';
import { readStoredToken, writeStoredToken, clearStoredToken } from './tokenStorage.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => readStoredToken());

  const login = useCallback(async (username, password) => {
    const { token: newToken } = await apiClient.login(username, password);
    writeStoredToken(newToken);
    setToken(newToken);
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
  }, []);

  const value = useMemo(() => ({ token, login, logout }), [token, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider');
  }
  return context;
}
```

- [ ] **Step 2: Implement `frontend/src/views/LoginView.jsx`**

```jsx
import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';

export default function LoginView() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.detail || 'Usuario o contraseña incorrectos.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-view">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>me-alcanza</h1>
        <label>
          Usuario
          <input value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p className="login-error">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
```

This task has no automated tests (React components — see Global
Constraints) and no standalone manual check either: `LoginView` isn't
mounted by anything until `App.jsx` exists in Task 7, so its manual
verification happens there (Task 7, Step 4) and end-to-end in Task 9.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/auth/AuthContext.jsx frontend/src/views/LoginView.jsx
git commit -m "feat: add AuthContext and LoginView"
```

---

## Task 6: `ChatView` — A2UI rendering + chat input + action wiring

**Files:**
- Create: `frontend/src/views/ChatView.jsx`

**Interfaces:**
- Consumes: `apiClient` (Task 2), `useAuth()` (Task 5), `createActionHandler` (Task 4), `MessageProcessor` from `@a2ui/web_core/v0_9`, `A2uiSurface`/`basicCatalog` from `@a2ui/react/v0_9`, `injectStyles`/`removeStyles` from `@a2ui/react/styles`.
- Produces: `ChatView` default export — rendered by `App.jsx` (Task 7) when `token` is set.

No automated tests for this task (React component — see Global Constraints); verified manually in Task 9 against the real backend.

- [ ] **Step 1: Implement `frontend/src/views/ChatView.jsx`**

```jsx
import { useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface, basicCatalog } from '@a2ui/react/v0_9';
import { injectStyles, removeStyles } from '@a2ui/react/styles';
import { apiClient } from '../api/client.js';
import { createActionHandler } from '../chat/actionHandler.js';
import { useAuth } from '../auth/AuthContext.jsx';

export default function ChatView() {
  const { token, logout } = useAuth();
  const [mensaje, setMensaje] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [surfaces, setSurfaces] = useState([]);

  function handleApiError(err, fallback) {
    if (err?.status === 401) {
      logout();
      return;
    }
    setErrorMessage(err?.detail || fallback);
  }

  const processor = useMemo(() => {
    let proc;
    const handleAction = createActionHandler({
      confirmAction: (proposalId) => apiClient.confirmAction(token, proposalId),
      onMessages: (messages) => proc.processMessages(messages),
      onError: (err) => handleApiError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
    });
    proc = new MessageProcessor([basicCatalog], handleAction);
    return proc;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    injectStyles();
    return () => removeStyles();
  }, []);

  useEffect(() => {
    const sync = () => setSurfaces(Array.from(processor.model.surfacesMap.values()));
    sync();
    const createdSub = processor.onSurfaceCreated(sync);
    const deletedSub = processor.onSurfaceDeleted(sync);
    return () => {
      createdSub.unsubscribe();
      deletedSub.unsubscribe();
    };
  }, [processor]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!mensaje.trim() || sending) {
      return;
    }
    setSending(true);
    setErrorMessage(null);
    try {
      const { a2ui_messages } = await apiClient.sendMessage(token, mensaje);
      processor.processMessages(a2ui_messages);
      setMensaje('');
    } catch (err) {
      handleApiError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-view">
      <header className="chat-header">
        <span>me-alcanza</span>
        <button type="button" onClick={logout}>
          Salir
        </button>
      </header>
      <main className="chat-surfaces">
        {surfaces.length === 0 && (
          <p className="chat-empty">Escribe tu primer mensaje para empezar.</p>
        )}
        {surfaces.map((surface) => (
          <A2uiSurface key={surface.id} surface={surface} />
        ))}
      </main>
      {errorMessage && <p className="chat-error">{errorMessage}</p>}
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={mensaje}
          onChange={(event) => setMensaje(event.target.value)}
          placeholder="Escribe tu mensaje..."
          disabled={sending}
        />
        <button type="submit" disabled={sending}>
          {sending ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/ChatView.jsx
git commit -m "feat: add ChatView with A2UI surface rendering and action wiring"
```

---

## Task 7: Wire `App.jsx` / `main.jsx` and remove template boilerplate

**Files:**
- Modify: `frontend/src/App.jsx` (overwrite entirely)
- Modify: `frontend/src/main.jsx`

**Interfaces:**
- Consumes: `AuthProvider`/`useAuth` (Task 5), `LoginView` (Task 5), `ChatView` (Task 6).
- Produces: the mounted app — the deliverable this task's manual verification checks.

- [ ] **Step 1: Overwrite `frontend/src/App.jsx`**

```jsx
import { AuthProvider, useAuth } from './auth/AuthContext.jsx';
import LoginView from './views/LoginView.jsx';
import ChatView from './views/ChatView.jsx';

function AppShell() {
  const { token } = useAuth();
  return token ? <ChatView /> : <LoginView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
```

- [ ] **Step 2: Confirm `frontend/src/main.jsx` still matches this shape (it should, unchanged from the scaffold)**

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

If it differs, overwrite it to match exactly.

- [ ] **Step 3: Create `frontend/.env` from the example (not committed — matches root `.gitignore`'s `.env` pattern)**

```bash
cp frontend/.env.example frontend/.env
```

- [ ] **Step 4: Manual verification — login flow**

Run: `cd frontend && npm run dev`, open the printed local URL (backend must NOT be running yet for this step — that's fine, login will fail with a network error, which is expected).
Expected: the page shows the login form (`LoginView`), not a blank page or crash.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx
git commit -m "feat: wire App shell to switch between LoginView and ChatView"
```

---

## Task 8: Styling pass — palette, typography, and shell layout

**Files:**
- Modify: `frontend/src/index.css` (overwrite entirely)

**Interfaces:**
- Consumes: the CSS custom properties `@a2ui/web_core`'s `basicCatalog` reads from `:root` (`--a2ui-color-*`, `--a2ui-font-*`, `--a2ui-spacing-*`, `--a2ui-border*`, `--a2ui-grid-base`, `--a2ui-line-height-*`) — confirmed by inspecting `@a2ui/web_core`'s `basic_catalog/styles/default.js`.
- Produces: the visual identity for `LoginView`/`ChatView`'s shell (the A2UI-rendered cards pick up the same palette automatically through those variables).

- [ ] **Step 1: Overwrite `frontend/src/index.css`**

```css
html:root {
  --a2ui-color-primary: #0f6e5c;
  --a2ui-color-secondary: #f2a541;
  --a2ui-color-background: #f7f5f0;
  --a2ui-color-surface: #ffffff;
  --a2ui-color-border: #d8d3c7;
  --a2ui-color-input: #ffffff;
  --a2ui-color-on-background: #1f2421;
  --a2ui-color-on-surface: #1f2421;
  --a2ui-color-on-primary: #ffffff;
  --a2ui-color-on-secondary: #1f2421;
  --a2ui-color-on-input: #1f2421;
  --a2ui-border-radius: 12px;
  --a2ui-border-width: 1px;
  --a2ui-font-family-title: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: var(--a2ui-font-family-title);
  background: var(--a2ui-color-background);
  color: var(--a2ui-color-on-background);
}

#root {
  min-height: 100vh;
}

.login-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--a2ui-spacing-l);
}

.login-form {
  width: 100%;
  max-width: 360px;
  background: var(--a2ui-color-surface);
  border: var(--a2ui-border-width) solid var(--a2ui-color-border);
  border-radius: var(--a2ui-border-radius);
  padding: var(--a2ui-spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--a2ui-spacing-m);
}

.login-form h1 {
  margin: 0 0 var(--a2ui-spacing-s);
  font-size: var(--a2ui-font-size-2xl);
  color: var(--a2ui-color-primary);
}

.login-form label {
  display: flex;
  flex-direction: column;
  gap: var(--a2ui-spacing-xs);
  font-size: var(--a2ui-font-size-s);
}

.login-form input {
  padding: var(--a2ui-spacing-s);
  border: var(--a2ui-border-width) solid var(--a2ui-color-border);
  border-radius: calc(var(--a2ui-border-radius) / 2);
  font-size: var(--a2ui-font-size-m);
}

.login-form button,
.chat-input button {
  padding: var(--a2ui-spacing-s) var(--a2ui-spacing-m);
  border: none;
  border-radius: calc(var(--a2ui-border-radius) / 2);
  background: var(--a2ui-color-primary);
  color: var(--a2ui-color-on-primary);
  font-size: var(--a2ui-font-size-m);
  cursor: pointer;
}

.login-form button:disabled,
.chat-input button:disabled {
  opacity: 0.6;
  cursor: default;
}

.login-error,
.chat-error {
  color: #b3261e;
  font-size: var(--a2ui-font-size-s);
}

.chat-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--a2ui-spacing-m) var(--a2ui-spacing-l);
  background: var(--a2ui-color-surface);
  border-bottom: var(--a2ui-border-width) solid var(--a2ui-color-border);
  font-size: var(--a2ui-font-size-l);
  font-weight: 600;
  color: var(--a2ui-color-primary);
}

.chat-header button {
  background: none;
  border: var(--a2ui-border-width) solid var(--a2ui-color-border);
  border-radius: calc(var(--a2ui-border-radius) / 2);
  padding: var(--a2ui-spacing-xs) var(--a2ui-spacing-m);
  cursor: pointer;
  font-size: var(--a2ui-font-size-s);
}

.chat-surfaces {
  flex: 1;
  overflow-y: auto;
  padding: var(--a2ui-spacing-l);
  display: flex;
  flex-direction: column;
  gap: var(--a2ui-spacing-m);
}

.chat-empty {
  opacity: 0.6;
}

.chat-input {
  display: flex;
  gap: var(--a2ui-spacing-s);
  padding: var(--a2ui-spacing-m) var(--a2ui-spacing-l);
  background: var(--a2ui-color-surface);
  border-top: var(--a2ui-border-width) solid var(--a2ui-color-border);
}

.chat-input input {
  flex: 1;
  padding: var(--a2ui-spacing-s);
  border: var(--a2ui-border-width) solid var(--a2ui-color-border);
  border-radius: calc(var(--a2ui-border-radius) / 2);
  font-size: var(--a2ui-font-size-m);
}
```

- [ ] **Step 2: Manual verification**

Run: `cd frontend && npm run dev`, open the printed local URL.
Expected: the login form is centered, uses the teal/amber palette above (not browser defaults), and the button/inputs are styled.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: apply palette and shell layout for login and chat views"
```

---

## Task 9: End-to-end manual verification against the real backend + README

**Files:**
- Create: `frontend/README.md`

**Interfaces:**
- Consumes: the entire app built in Tasks 1-8, plus the already-implemented backend (`src/me_alcanza/backend/`).

- [ ] **Step 1: Create `frontend/README.md`**

```markdown
# me-alcanza — frontend (React + Vite)

Cliente React (JavaScript, sin TypeScript) para el backend de
`me-alcanza`. Renderiza las superficies A2UI que arma el agente y
confirma propuestas de acción (apartado de ahorro / transferencia).

## Requisitos

- Node.js y `npm`.
- El backend corriendo en `http://localhost:8000` (ver raíz del repo:
  `uv run me-alcanza`, con `.env` configurado con
  `GOOGLE_AI_STUDIO_API_KEY`, `GEMINI_MODEL`, `JWT_SECRET`).

## Uso

```bash
cd frontend
cp .env.example .env   # ajusta VITE_API_BASE_URL si el backend no está en localhost:8000
npm install
npm run dev
```

Abre la URL que imprime Vite (usualmente `http://localhost:5173`).

Usuarios demo (ya sembrados en la base de datos simulada del backend):

- `ana` / `pass123`
- `luis` / `pass456`

## Pruebas

```bash
npm test
```

Corre los tests unitarios de los módulos JavaScript puros
(`api/client.js`, `auth/tokenStorage.js`, `chat/actionHandler.js`). Los
componentes de React (`LoginView`, `ChatView`, `App`) se verifican
manualmente en el navegador — ver los dos flujos abajo.

## Verificación manual de los dos flujos núcleo

Con el backend corriendo y `npm run dev` activo:

1. **Afford-check + apartado**: inicia sesión como `ana` / `pass123`,
   escribe "¿me alcanza para el concierto del 13 de octubre?". Debe
   aparecer una tarjeta con el veredicto y, si no alcanza, un botón para
   activar el apartado sugerido. Al hacer click, debe aparecer una
   tarjeta de confirmación (el apartado se creó de verdad en la DB
   simulada del backend).
2. **Transferencia con desambiguación**: en la misma sesión, escribe
   "deposítale 500 a mi hermano Pepe". Deben aparecer dos tarjetas de
   confirmación (dos contactos candidatos). Confirma una: debe aparecer
   la tarjeta de confirmación de esa transferencia específica.

Ambos flujos deben sobrevivir un refresh de página sin perder la sesión
(el token persiste en `localStorage`); cerrar sesión con "Salir" debe
regresar a la pantalla de login y limpiar el token.
```

- [ ] **Step 2: Run the full unit test suite**

Run: `cd frontend && npm test`
Expected: PASS — all Vitest suites from Tasks 2-4 green (12 tests total: 5 in `client.test.js`, 4 in `tokenStorage.test.js`, 3 in `actionHandler.test.js`).

- [ ] **Step 3: Run the production build**

Run: `cd frontend && npm run build`
Expected: PASS — no errors, `dist/` produced.

- [ ] **Step 4: Manual end-to-end verification against the real backend**

In one terminal, from the repo root: `uv run me-alcanza` (requires `.env` at the repo root with a real `GOOGLE_AI_STUDIO_API_KEY`, `GEMINI_MODEL`, `JWT_SECRET` — already present in this repo's `.env`).
In another terminal: `cd frontend && npm run dev`.
Follow the two flows documented in `frontend/README.md` step 1 above, end to end, confirming both proposals for real.
Expected: both flows complete without a frontend crash, unhandled promise rejection in the console, or a stuck "Enviando..."/"Entrando..." button state.

- [ ] **Step 5: Commit**

```bash
git add frontend/README.md
git commit -m "docs: add frontend README with setup and manual verification steps"
```
