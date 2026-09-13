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

  async function patch(path, { token, body } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(body ?? {}),
    });
    if (!response.ok) {
      throw new ApiError(response.status, await parseErrorDetail(response));
    }
    return response.json();
  }

  async function del(path, { token } = {}) {
    const headers = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(`${baseUrl}${path}`, { method: 'DELETE', headers });
    if (!response.ok) {
      throw new ApiError(response.status, await parseErrorDetail(response));
    }
    // 204 No Content: no hay body que parsear.
    return response.status === 204 ? undefined : response.json();
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
    createMeta: (token, meta) => post('/api/metas', { token, body: meta }),
    updateMeta: (token, metaId, cambios) => patch(`/api/metas/${metaId}`, { token, body: cambios }),
    deleteMeta: (token, metaId) => del(`/api/metas/${metaId}`, { token }),

    getApartados: (token) => get('/api/apartados', { token }),
    createApartado: (token, apartado) => post('/api/apartados', { token, body: apartado }),
    cancelarApartado: (token, apartadoId) => post(`/api/apartados/${apartadoId}/cancelar`, { token }),

    getGastosFijos: (token) => get('/api/gastos-fijos', { token }),
    createGastoFijo: (token, gasto) => post('/api/gastos-fijos', { token, body: gasto }),
    updateGastoFijo: (token, gastoId, cambios) => patch(`/api/gastos-fijos/${gastoId}`, { token, body: cambios }),
    deleteGastoFijo: (token, gastoId) => del(`/api/gastos-fijos/${gastoId}`, { token }),

    getIngresosProgramados: (token) => get('/api/ingresos-programados', { token }),
    createIngresoProgramado: (token, ingreso) => post('/api/ingresos-programados', { token, body: ingreso }),
    updateIngresoProgramado: (token, ingresoId, cambios) =>
      patch(`/api/ingresos-programados/${ingresoId}`, { token, body: cambios }),
    deleteIngresoProgramado: (token, ingresoId) => del(`/api/ingresos-programados/${ingresoId}`, { token }),

    getContactos: (token) => get('/api/contactos', { token }),
    createContacto: (token, contacto) => post('/api/contactos', { token, body: contacto }),
    updateContacto: (token, contactoId, cambios) => patch(`/api/contactos/${contactoId}`, { token, body: cambios }),
    deleteContacto: (token, contactoId) => del(`/api/contactos/${contactoId}`, { token }),

    getSugerencias: (token) => get('/api/sugerencias', { token }),
    atenderSugerencia: (token, sugerenciaId) =>
      post(`/api/sugerencias/${sugerenciaId}/atender`, { token }),
    descartarSugerencia: (token, sugerenciaId) =>
      post(`/api/sugerencias/${sugerenciaId}/descartar`, { token }),
    getPropuestaSugerencia: (token, sugerenciaId) =>
      get(`/api/sugerencias/${sugerenciaId}/propuesta`, { token }),
  };
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient = createApiClient(DEFAULT_BASE_URL);
