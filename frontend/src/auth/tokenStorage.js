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
