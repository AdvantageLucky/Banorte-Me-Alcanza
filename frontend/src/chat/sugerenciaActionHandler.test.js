import { describe, it, expect, vi } from 'vitest';
import { createSugerenciaActionHandler } from './sugerenciaActionHandler.js';

function makeAction(overrides = {}) {
  return {
    name: 'atender_sugerencia',
    context: { sugerenciaId: 7 },
    surfaceId: 'main',
    sourceComponentId: 'btn-1',
    timestamp: '2026-09-12T00:00:00Z',
    ...overrides,
  };
}

function makeHandler(overrides = {}) {
  const atenderSugerencia = vi.fn().mockResolvedValue({});
  const descartarSugerencia = vi.fn().mockResolvedValue({});
  const requestConfirmacion = vi.fn();
  const onResuelta = vi.fn();
  const onError = vi.fn();
  const handleAction = createSugerenciaActionHandler({
    atenderSugerencia,
    descartarSugerencia,
    requestConfirmacion,
    onResuelta,
    onError,
    ...overrides,
  });
  return { handleAction, atenderSugerencia, descartarSugerencia, requestConfirmacion, onResuelta, onError };
}

describe('createSugerenciaActionHandler', () => {
  it('ignora acciones que no sean atender_sugerencia ni descartar_sugerencia', async () => {
    const { handleAction, atenderSugerencia, descartarSugerencia, requestConfirmacion } = makeHandler();

    await handleAction(makeAction({ name: 'confirmar_accion' }));

    expect(atenderSugerencia).not.toHaveBeenCalled();
    expect(descartarSugerencia).not.toHaveBeenCalled();
    expect(requestConfirmacion).not.toHaveBeenCalled();
  });

  it('descartar_sugerencia se ejecuta directo, sin pasar por el modal', async () => {
    const { handleAction, descartarSugerencia, atenderSugerencia, requestConfirmacion, onResuelta } =
      makeHandler();

    await handleAction(makeAction({ name: 'descartar_sugerencia', context: { sugerenciaId: 3 } }));

    expect(descartarSugerencia).toHaveBeenCalledWith(3);
    expect(atenderSugerencia).not.toHaveBeenCalled();
    expect(requestConfirmacion).not.toHaveBeenCalled();
    expect(onResuelta).toHaveBeenCalledWith(3);
  });

  it('atender_sugerencia pide confirmación en vez de ejecutar directo', async () => {
    const { handleAction, atenderSugerencia, requestConfirmacion } = makeHandler();

    await handleAction(makeAction());

    expect(atenderSugerencia).not.toHaveBeenCalled();
    expect(requestConfirmacion).toHaveBeenCalledWith(
      expect.objectContaining({ sugerenciaId: 7, onConfirm: expect.any(Function), onCancel: expect.any(Function) }),
    );
  });

  it('confirmar en el modal sí llama a atenderSugerencia y avisa que se resolvió', async () => {
    const { handleAction, atenderSugerencia, requestConfirmacion, onResuelta } = makeHandler();

    await handleAction(makeAction());
    const { onConfirm } = requestConfirmacion.mock.calls[0][0];
    await onConfirm();

    expect(atenderSugerencia).toHaveBeenCalledWith(7);
    expect(onResuelta).toHaveBeenCalledWith(7);
  });

  it('reporta el error si atenderSugerencia falla tras confirmar', async () => {
    const failure = new Error('boom');
    const { handleAction, requestConfirmacion, onError, onResuelta } = makeHandler({
      atenderSugerencia: vi.fn().mockRejectedValue(failure),
    });

    await handleAction(makeAction());
    const { onConfirm } = requestConfirmacion.mock.calls[0][0];
    await onConfirm();

    expect(onError).toHaveBeenCalledWith(failure);
    expect(onResuelta).not.toHaveBeenCalled();
  });

  it('reporta el error si descartarSugerencia falla', async () => {
    const failure = new Error('boom');
    const { handleAction, onError, onResuelta } = makeHandler({
      descartarSugerencia: vi.fn().mockRejectedValue(failure),
    });

    await handleAction(makeAction({ name: 'descartar_sugerencia' }));

    expect(onError).toHaveBeenCalledWith(failure);
    expect(onResuelta).not.toHaveBeenCalled();
  });
});
