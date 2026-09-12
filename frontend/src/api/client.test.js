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

  describe('recursos de "Yo" (solo lectura)', () => {
    it.each([
      ['getCuenta', '/api/cuenta', { titular: 'Ana', numero_cuenta: '123', saldo: 100, moneda: 'MXN' }],
      ['getMovimientos', '/api/movimientos', [{ fecha: '2026-01-01', concepto: 'Café', monto: -50 }]],
      ['getMetas', '/api/metas', [{ id: 1, descripcion: 'Viaje', monto_objetivo: 1000, fecha_objetivo: '2026-12-01', monto_ahorrado: 200 }]],
      ['getApartados', '/api/apartados', [{ id: 1, meta_id: 1, monto_por_periodo: 100, periodicidad: 'mensual', fecha_inicio: '2026-01-01', estado: 'activo' }]],
      ['getGastosFijos', '/api/gastos-fijos', [{ id: 1, concepto: 'Renta', monto: 5000, frecuencia: 'mensual', proxima_fecha: '2026-10-01' }]],
      ['getIngresosProgramados', '/api/ingresos-programados', [{ id: 1, descripcion: 'Nómina', monto: 15000, frecuencia: 'quincenal', proxima_fecha: '2026-09-30' }]],
    ])('%s hace un GET autenticado a %s', async (method, path, responseBody) => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => responseBody,
      });
      const client = createApiClient('http://api.test');

      const result = await client[method]('jwt-123');

      expect(result).toEqual(responseBody);
      expect(fetchMock).toHaveBeenCalledWith(
        `http://api.test${path}`,
        expect.objectContaining({
          method: 'GET',
          headers: { Authorization: 'Bearer jwt-123' },
        }),
      );
    });

    it('propaga un ApiException cuando el GET responde con error', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Token inválido' }),
      });
      const client = createApiClient('http://api.test');

      await expect(client.getCuenta('jwt-expired')).rejects.toMatchObject({
        status: 401,
        detail: 'Token inválido',
      });
    });
  });
});
