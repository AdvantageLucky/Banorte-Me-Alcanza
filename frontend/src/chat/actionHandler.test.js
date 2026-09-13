import { describe, it, expect, vi } from 'vitest';
import { createActionHandler, CONFIRM_ACTION_NAME, REJECT_ACTION_NAME } from './actionHandler.js';

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

const resueltoMessage = { version: 'v0.9', updateDataModel: { surfaceId: 'main', path: '/resuelto', value: true } };

describe('createActionHandler', () => {
  it('ignores actions with a name other than confirmar_accion or rechazar_accion', async () => {
    const confirmAction = vi.fn();
    const rejectAction = vi.fn();
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ confirmAction, rejectAction, onMessages, onError });

    await handleAction(makeAction({ name: 'otra_accion' }));

    expect(confirmAction).not.toHaveBeenCalled();
    expect(rejectAction).not.toHaveBeenCalled();
    expect(onMessages).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it('confirms the proposal from context.proposalId and marks the original card as resuelta', async () => {
    const confirmAction = vi.fn().mockResolvedValue({ a2ui_messages: [{ foo: 'bar' }] });
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ confirmAction, onMessages, onError });

    await handleAction(makeAction());

    expect(confirmAction).toHaveBeenCalledWith('prop-1', undefined);
    expect(onMessages).toHaveBeenCalledWith([resueltoMessage, { foo: 'bar' }]);
    expect(onError).not.toHaveBeenCalled();
  });

  it('forwards any edited fields alongside proposalId as a separate context argument', async () => {
    const confirmAction = vi.fn().mockResolvedValue({ a2ui_messages: [] });
    const handleAction = createActionHandler({ confirmAction, onMessages: vi.fn(), onError: vi.fn() });

    await handleAction(
      makeAction({ context: { proposalId: 'prop-1', nombre: 'Mamá', cuenta_destino: '1234567890' } }),
    );

    expect(confirmAction).toHaveBeenCalledWith('prop-1', {
      nombre: 'Mamá',
      cuenta_destino: '1234567890',
    });
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

  it('rejects the proposal from context.proposalId and marks the original card as resuelta', async () => {
    const rejectAction = vi.fn().mockResolvedValue({ a2ui_messages: [{ foo: 'cancelado' }] });
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ rejectAction, onMessages, onError });

    await handleAction(makeAction({ name: REJECT_ACTION_NAME }));

    expect(rejectAction).toHaveBeenCalledWith('prop-1');
    expect(onMessages).toHaveBeenCalledWith([resueltoMessage, { foo: 'cancelado' }]);
    expect(onError).not.toHaveBeenCalled();
  });

  it('reports an error when rejecting the proposal fails, without touching onMessages', async () => {
    const failure = new Error('boom');
    const rejectAction = vi.fn().mockRejectedValue(failure);
    const onMessages = vi.fn();
    const onError = vi.fn();
    const handleAction = createActionHandler({ rejectAction, onMessages, onError });

    await handleAction(makeAction({ name: REJECT_ACTION_NAME }));

    expect(onError).toHaveBeenCalledWith(failure);
    expect(onMessages).not.toHaveBeenCalled();
  });
});
