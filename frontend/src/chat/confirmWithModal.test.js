import { describe, it, expect, vi } from 'vitest';
import { createConfirmActionWithModal } from './confirmWithModal.js';

describe('createConfirmActionWithModal', () => {
  it('pide el resumen autoritativo antes de mostrar la confirmación', async () => {
    const getPropuesta = vi.fn().mockResolvedValue({ tipo: 'transferencia', resumen: 'Transferir $500.00 a José Ramírez' });
    const confirmAction = vi.fn();
    const requestConfirmation = vi.fn();
    const confirmActionWithModal = createConfirmActionWithModal({
      getPropuesta,
      confirmAction,
      requestConfirmation,
    });

    confirmActionWithModal('prop-1');
    await Promise.resolve();
    await Promise.resolve();

    expect(getPropuesta).toHaveBeenCalledWith('prop-1');
    expect(requestConfirmation).toHaveBeenCalledWith(
      expect.objectContaining({ resumen: 'Transferir $500.00 a José Ramírez' }),
    );
  });

  it('ejecuta confirmAction y resuelve solo cuando el usuario confirma en el modal', async () => {
    const getPropuesta = vi.fn().mockResolvedValue({ tipo: 'transferencia', resumen: 'Transferir $500.00' });
    const confirmAction = vi.fn().mockResolvedValue({ a2ui_messages: [{ foo: 'bar' }] });
    let captured;
    const requestConfirmation = vi.fn((payload) => {
      captured = payload;
    });
    const confirmActionWithModal = createConfirmActionWithModal({
      getPropuesta,
      confirmAction,
      requestConfirmation,
    });

    const resultPromise = confirmActionWithModal('prop-1');
    await Promise.resolve();
    await Promise.resolve();

    expect(confirmAction).not.toHaveBeenCalled();
    await captured.onConfirm();

    await expect(resultPromise).resolves.toEqual({ a2ui_messages: [{ foo: 'bar' }] });
    expect(confirmAction).toHaveBeenCalledWith('prop-1');
  });

  it('rechaza con un error silencioso cuando el usuario cancela, sin llamar confirmAction', async () => {
    const getPropuesta = vi.fn().mockResolvedValue({ tipo: 'transferencia', resumen: 'Transferir $500.00' });
    const confirmAction = vi.fn();
    let captured;
    const requestConfirmation = vi.fn((payload) => {
      captured = payload;
    });
    const confirmActionWithModal = createConfirmActionWithModal({
      getPropuesta,
      confirmAction,
      requestConfirmation,
    });

    const resultPromise = confirmActionWithModal('prop-1');
    await Promise.resolve();
    await Promise.resolve();

    captured.onCancel();

    await expect(resultPromise).rejects.toMatchObject({ silent: true });
    expect(confirmAction).not.toHaveBeenCalled();
  });

  it('propaga el error de confirmAction cuando la confirmación falla', async () => {
    const getPropuesta = vi.fn().mockResolvedValue({ tipo: 'transferencia', resumen: 'Transferir $500.00' });
    const failure = new Error('boom');
    const confirmAction = vi.fn().mockRejectedValue(failure);
    let captured;
    const requestConfirmation = vi.fn((payload) => {
      captured = payload;
    });
    const confirmActionWithModal = createConfirmActionWithModal({
      getPropuesta,
      confirmAction,
      requestConfirmation,
    });

    const resultPromise = confirmActionWithModal('prop-1');
    await Promise.resolve();
    await Promise.resolve();

    await captured.onConfirm();

    await expect(resultPromise).rejects.toBe(failure);
  });
});
