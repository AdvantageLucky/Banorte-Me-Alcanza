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

  async function get(path, { token } = {}) {
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${baseUrl}${path}`, { method: 'GET', headers });
    if (!response.ok) {
      throw new ApiError(response.status, await parseErrorDetail(response));
    }
    return response.json();
  }

  return {
    login: (username, password) => post('/api/login', { body: { username, password } }),
    sendMessage: (token, mensaje, conversacionId) =>
      post('/api/chat', { token, body: { mensaje, conversacion_id: conversacionId ?? null } }),
    getConversaciones: (token) => get('/api/conversaciones', { token }),
    getMensajesConversacion: (token, conversacionId) =>
      get(`/api/conversaciones/${conversacionId}/mensajes`, { token }),
    confirmAction: (token, proposalId) =>
      post('/api/confirm-action', { token, body: { proposal_id: proposalId } }),
    getPropuesta: (token, proposalId) => get(`/api/propuestas/${proposalId}`, { token }),
    getCuenta: (token) => get('/api/cuenta', { token }),
    getMovimientos: (token) => get('/api/movimientos', { token }),
    getMetas: (token) => get('/api/metas', { token }),
    getApartados: (token) => get('/api/apartados', { token }),
    getGastosFijos: (token) => get('/api/gastos-fijos', { token }),
    getIngresosProgramados: (token) => get('/api/ingresos-programados', { token }),
    getSugerencias: (token) => get('/api/sugerencias', { token }),
    atenderSugerencia: (token, sugerenciaId) =>
      post(`/api/sugerencias/${sugerenciaId}/atender`, { token }),
    descartarSugerencia: (token, sugerenciaId) =>
      post(`/api/sugerencias/${sugerenciaId}/descartar`, { token }),
  };
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient = createApiClient(DEFAULT_BASE_URL);
