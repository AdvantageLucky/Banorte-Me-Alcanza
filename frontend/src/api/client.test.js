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

  it('sends the bearer token and mensaje on /api/chat, with no conversacion_id by default', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [], conversacion_id: 1 }),
    });
    const client = createApiClient('http://api.test');

    await client.sendMessage('jwt-123', '¿me alcanza para el concierto?');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/chat',
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
        body: JSON.stringify({ mensaje: '¿me alcanza para el concierto?', conversacion_id: null }),
      }),
    );
  });

  it('sends the given conversacion_id on /api/chat so the backend continues that same thread', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [], conversacion_id: 7 }),
    });
    const client = createApiClient('http://api.test');

    await client.sendMessage('jwt-123', 'otro mensaje', 7);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/chat',
      expect.objectContaining({
        body: JSON.stringify({ mensaje: 'otro mensaje', conversacion_id: 7 }),
      }),
    );
  });

  it('getConversaciones hace un GET autenticado a /api/conversaciones', async () => {
    const conversaciones = [{ id: 1, titulo: 'Nueva conversación', created_at: '2026-09-12T10:00:00', updated_at: '2026-09-12T10:00:00' }];
    fetchMock.mockResolvedValue({ ok: true, json: async () => conversaciones });
    const client = createApiClient('http://api.test');

    const result = await client.getConversaciones('jwt-123');

    expect(result).toEqual(conversaciones);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/conversaciones',
      expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
    );
  });

  it('getMensajesConversacion hace un GET autenticado a /api/conversaciones/{id}/mensajes', async () => {
    const mensajes = [{ rol: 'user', contenido: 'hola', created_at: '2026-09-12T10:00:00', a2ui_json: null }];
    fetchMock.mockResolvedValue({ ok: true, json: async () => mensajes });
    const client = createApiClient('http://api.test');

    const result = await client.getMensajesConversacion('jwt-123', 7);

    expect(result).toEqual(mensajes);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/conversaciones/7/mensajes',
      expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
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
        body: JSON.stringify({ proposal_id: 'prop-1', context: null }),
      }),
    );
  });

  it('sends the edited fields as context on /api/confirm-action when provided', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [] }),
    });
    const client = createApiClient('http://api.test');

    await client.confirmAction('jwt-123', 'prop-1', { nombre: 'Mamá' });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/confirm-action',
      expect.objectContaining({
        body: JSON.stringify({ proposal_id: 'prop-1', context: { nombre: 'Mamá' } }),
      }),
    );
  });

  it('sends proposal_id on /api/reject-action', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ a2ui_messages: [] }),
    });
    const client = createApiClient('http://api.test');

    await client.rejectAction('jwt-123', 'prop-1');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/reject-action',
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

  it('getPropuesta hace un GET autenticado a /api/propuestas/{id}', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ tipo: 'transferencia', resumen: 'Transferir $500.00 a José Ramírez' }),
    });
    const client = createApiClient('http://api.test');

    const result = await client.getPropuesta('jwt-123', 'prop-1');

    expect(result).toEqual({ tipo: 'transferencia', resumen: 'Transferir $500.00 a José Ramírez' });
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/propuestas/prop-1',
      expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
    );
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

  describe('CRUD del core bancario', () => {
    it('createMeta hace POST a /api/metas con el body de la meta', async () => {
      const creada = { id: 1, descripcion: 'Viaje', monto_objetivo: 1000, fecha_objetivo: '2026-12-01', monto_ahorrado: 0 };
      fetchMock.mockResolvedValue({ ok: true, json: async () => creada });
      const client = createApiClient('http://api.test');

      const result = await client.createMeta('jwt-123', {
        descripcion: 'Viaje',
        monto_objetivo: 1000,
        fecha_objetivo: '2026-12-01',
      });

      expect(result).toEqual(creada);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/metas',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
          body: JSON.stringify({ descripcion: 'Viaje', monto_objetivo: 1000, fecha_objetivo: '2026-12-01' }),
        }),
      );
    });

    it('updateMeta hace PATCH a /api/metas/{id} con solo los campos cambiados', async () => {
      const actualizada = { id: 1, descripcion: 'Viaje', monto_objetivo: 1500, fecha_objetivo: '2026-12-01', monto_ahorrado: 0 };
      fetchMock.mockResolvedValue({ ok: true, json: async () => actualizada });
      const client = createApiClient('http://api.test');

      const result = await client.updateMeta('jwt-123', 1, { monto_objetivo: 1500 });

      expect(result).toEqual(actualizada);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/metas/1',
        expect.objectContaining({
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
          body: JSON.stringify({ monto_objetivo: 1500 }),
        }),
      );
    });

    it('deleteMeta hace DELETE a /api/metas/{id} y no intenta parsear un body en 204', async () => {
      fetchMock.mockResolvedValue({ ok: true, status: 204 });
      const client = createApiClient('http://api.test');

      const result = await client.deleteMeta('jwt-123', 1);

      expect(result).toBeUndefined();
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/metas/1',
        expect.objectContaining({ method: 'DELETE', headers: { Authorization: 'Bearer jwt-123' } }),
      );
    });

    it('createApartado hace POST a /api/apartados', async () => {
      const creado = { id: 1, meta_id: 1, monto_por_periodo: 100, periodicidad: 'mensual', fecha_inicio: '2026-09-12', estado: 'activo' };
      fetchMock.mockResolvedValue({ ok: true, json: async () => creado });
      const client = createApiClient('http://api.test');

      await client.createApartado('jwt-123', { meta_id: 1, monto_por_periodo: 100, periodicidad: 'mensual' });

      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/apartados',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ meta_id: 1, monto_por_periodo: 100, periodicidad: 'mensual' }),
        }),
      );
    });

    it('cancelarApartado hace POST a /api/apartados/{id}/cancelar sin body', async () => {
      const cancelado = { id: 1, meta_id: 1, monto_por_periodo: 100, periodicidad: 'mensual', fecha_inicio: '2026-09-12', estado: 'cancelado' };
      fetchMock.mockResolvedValue({ ok: true, json: async () => cancelado });
      const client = createApiClient('http://api.test');

      const result = await client.cancelarApartado('jwt-123', 1);

      expect(result).toEqual(cancelado);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/apartados/1/cancelar',
        expect.objectContaining({ method: 'POST' }),
      );
    });

    it.each([
      ['createGastoFijo', 'updateGastoFijo', 'deleteGastoFijo', '/api/gastos-fijos'],
      ['createIngresoProgramado', 'updateIngresoProgramado', 'deleteIngresoProgramado', '/api/ingresos-programados'],
    ])('%s/%s/%s hacen POST/PATCH/DELETE a %s', async (createFn, updateFn, deleteFn, basePath) => {
      fetchMock.mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) });
      const client = createApiClient('http://api.test');

      await client[createFn]('jwt-123', { concepto: 'Renta', monto: 5000, frecuencia: 'mensual', proxima_fecha: '2026-10-01' });
      expect(fetchMock).toHaveBeenCalledWith(`http://api.test${basePath}`, expect.objectContaining({ method: 'POST' }));

      await client[updateFn]('jwt-123', 1, { monto: 5500 });
      expect(fetchMock).toHaveBeenCalledWith(`http://api.test${basePath}/1`, expect.objectContaining({ method: 'PATCH' }));

      fetchMock.mockResolvedValue({ ok: true, status: 204 });
      await client[deleteFn]('jwt-123', 1);
      expect(fetchMock).toHaveBeenCalledWith(`http://api.test${basePath}/1`, expect.objectContaining({ method: 'DELETE' }));
    });

    it('getContactos hace un GET autenticado a /api/contactos', async () => {
      const contactos = [{ id: 1, nombre: 'José Ramírez', alias: 'Pepe', cuenta_destino: '9988776655', relacion: 'hermano' }];
      fetchMock.mockResolvedValue({ ok: true, json: async () => contactos });
      const client = createApiClient('http://api.test');

      const result = await client.getContactos('jwt-123');

      expect(result).toEqual(contactos);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/contactos',
        expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
      );
    });

    it('createContacto/updateContacto/deleteContacto hacen POST/PATCH/DELETE a /api/contactos', async () => {
      fetchMock.mockResolvedValue({ ok: true, json: async () => ({ id: 1 }) });
      const client = createApiClient('http://api.test');

      await client.createContacto('jwt-123', { nombre: 'Sofía', alias: 'Sofi', cuenta_destino: '111', relacion: 'amiga' });
      expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/contactos', expect.objectContaining({ method: 'POST' }));

      await client.updateContacto('jwt-123', 1, { alias: 'Sofi L.' });
      expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/contactos/1', expect.objectContaining({ method: 'PATCH' }));

      fetchMock.mockResolvedValue({ ok: true, status: 204 });
      await client.deleteContacto('jwt-123', 1);
      expect(fetchMock).toHaveBeenCalledWith('http://api.test/api/contactos/1', expect.objectContaining({ method: 'DELETE' }));
    });

    it('propaga un ApiException cuando el PATCH responde con error', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'monto debe ser mayor a cero' }),
      });
      const client = createApiClient('http://api.test');

      await expect(client.updateMeta('jwt-123', 1, { monto_objetivo: -5 })).rejects.toMatchObject({
        status: 400,
        detail: 'monto debe ser mayor a cero',
      });
    });
  });

  describe('sugerencias', () => {
    it('getSugerencias hace un GET autenticado a /api/sugerencias', async () => {
      const sugerencias = [
        { id: 1, tipo: 'meta_en_riesgo', entidad_id: '3', detalle: {}, estado: 'pendiente', created_at: '2026-09-12T10:00:00', resuelta_at: null },
      ];
      fetchMock.mockResolvedValue({ ok: true, json: async () => sugerencias });
      const client = createApiClient('http://api.test');

      const result = await client.getSugerencias('jwt-123');

      expect(result).toEqual(sugerencias);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/sugerencias',
        expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
      );
    });

    it('atenderSugerencia hace POST a /api/sugerencias/{id}/atender', async () => {
      const actualizada = { id: 1, tipo: 'meta_en_riesgo', entidad_id: '3', detalle: {}, estado: 'atendida', created_at: '2026-09-12T10:00:00', resuelta_at: '2026-09-12T11:00:00' };
      fetchMock.mockResolvedValue({ ok: true, json: async () => actualizada });
      const client = createApiClient('http://api.test');

      const result = await client.atenderSugerencia('jwt-123', 1);

      expect(result).toEqual(actualizada);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/sugerencias/1/atender',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
        }),
      );
    });

    it('descartarSugerencia hace POST a /api/sugerencias/{id}/descartar', async () => {
      const actualizada = { id: 2, tipo: 'gasto_fijo_proximo', entidad_id: '7', detalle: {}, estado: 'descartada', created_at: '2026-09-12T10:00:00', resuelta_at: '2026-09-12T11:00:00' };
      fetchMock.mockResolvedValue({ ok: true, json: async () => actualizada });
      const client = createApiClient('http://api.test');

      const result = await client.descartarSugerencia('jwt-123', 2);

      expect(result).toEqual(actualizada);
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/sugerencias/2/descartar',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer jwt-123' },
        }),
      );
    });

    it('getPropuestaSugerencia hace un GET autenticado a /api/sugerencias/{id}/propuesta', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ propuesta: 'Considera adelantar este pago.' }),
      });
      const client = createApiClient('http://api.test');

      const result = await client.getPropuestaSugerencia('jwt-123', 9);

      expect(result).toEqual({ propuesta: 'Considera adelantar este pago.' });
      expect(fetchMock).toHaveBeenCalledWith(
        'http://api.test/api/sugerencias/9/propuesta',
        expect.objectContaining({ method: 'GET', headers: { Authorization: 'Bearer jwt-123' } }),
      );
    });
  });
});
