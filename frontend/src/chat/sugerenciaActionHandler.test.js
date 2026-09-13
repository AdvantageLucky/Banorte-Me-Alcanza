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

describe('createSugerenciaActionHandler', () => {
  it('ignora acciones que no sean atender_sugerencia ni descartar_sugerencia', async () => {
    const atenderSugerencia = vi.fn();
    const descartarSugerencia = vi.fn();
    const onResuelta = vi.fn();
    const onError = vi.fn();
    const handleAction = createSugerenciaActionHandler({ atenderSugerencia, descartarSugerencia, onResuelta, onError });

    await handleAction(makeAction({ name: 'confirmar_accion' }));

    expect(atenderSugerencia).not.toHaveBeenCalled();
    expect(descartarSugerencia).not.toHaveBeenCalled();
    expect(onResuelta).not.toHaveBeenCalled();
  });

  it('llama a atenderSugerencia con el sugerenciaId y avisa que se resolvió', async () => {
    const atenderSugerencia = vi.fn().mockResolvedValue({});
    const descartarSugerencia = vi.fn();
    const onResuelta = vi.fn();
    const onError = vi.fn();
    const handleAction = createSugerenciaActionHandler({ atenderSugerencia, descartarSugerencia, onResuelta, onError });

    await handleAction(makeAction());

    expect(atenderSugerencia).toHaveBeenCalledWith(7);
    expect(descartarSugerencia).not.toHaveBeenCalled();
    expect(onResuelta).toHaveBeenCalledWith(7);
    expect(onError).not.toHaveBeenCalled();
  });

  it('llama a descartarSugerencia cuando la acción es descartar_sugerencia', async () => {
    const atenderSugerencia = vi.fn();
    const descartarSugerencia = vi.fn().mockResolvedValue({});
    const onResuelta = vi.fn();
    const onError = vi.fn();
    const handleAction = createSugerenciaActionHandler({ atenderSugerencia, descartarSugerencia, onResuelta, onError });

    await handleAction(makeAction({ name: 'descartar_sugerencia', context: { sugerenciaId: 3 } }));

    expect(descartarSugerencia).toHaveBeenCalledWith(3);
    expect(atenderSugerencia).not.toHaveBeenCalled();
    expect(onResuelta).toHaveBeenCalledWith(3);
  });

  it('reporta el error sin llamar a onResuelta cuando la llamada falla', async () => {
    const failure = new Error('boom');
    const atenderSugerencia = vi.fn().mockRejectedValue(failure);
    const descartarSugerencia = vi.fn();
    const onResuelta = vi.fn();
    const onError = vi.fn();
    const handleAction = createSugerenciaActionHandler({ atenderSugerencia, descartarSugerencia, onResuelta, onError });

    await handleAction(makeAction());

    expect(onError).toHaveBeenCalledWith(failure);
    expect(onResuelta).not.toHaveBeenCalled();
  });
});
