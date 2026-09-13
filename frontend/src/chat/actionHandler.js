export const CONFIRM_ACTION_NAME = 'confirmar_accion';

export function createActionHandler({ confirmAction, onMessages, onError }) {
  return async function handleAction(action) {
    if (action.name !== CONFIRM_ACTION_NAME) {
      return;
    }
    // El resto de action.context (además de proposalId) son los campos que
    // el modelo enlazó a TextField/DateTimeInput/etc en la tarjeta — a2ui_core
    // ya los resolvió contra el data model en vivo antes de emitir el evento,
    // así que lo que llega aquí es lo que el usuario realmente escribió, no
    // lo que el modelo propuso originalmente.
    const { proposalId, ...context } = action.context ?? {};
    const tieneContext = Object.keys(context).length > 0;
    try {
      const { a2ui_messages } = await confirmAction(proposalId, tieneContext ? context : undefined);
      onMessages(a2ui_messages);
    } catch (err) {
      onError(err);
    }
  };
}
