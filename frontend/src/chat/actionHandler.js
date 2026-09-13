export const CONFIRM_ACTION_NAME = 'confirmar_accion';
export const REJECT_ACTION_NAME = 'rechazar_accion';

// Marca la tarjeta ORIGINAL (no el mensaje nuevo de resultado) como resuelta,
// escribiendo directo al path que el system prompt instruye a inicializar en
// cada tarjeta de confirmación ('/resuelto'). El Button de esa tarjeta trae
// un `checks` que lo deshabilita cuando ese path es true — así el botón dejar
// de verse activo para siempre después de que la propuesta ya se usó, sin
// tener que rastrear estado aparte del propio data model de a2ui.
function marcarResueltoMessage(surfaceId) {
  return { version: 'v0.9', updateDataModel: { surfaceId, path: '/resuelto', value: true } };
}

export function createActionHandler({ confirmAction, rejectAction, onMessages, onError }) {
  return async function handleAction(action) {
    if (action.name === CONFIRM_ACTION_NAME) {
      // El resto de action.context (además de proposalId) son los campos que
      // el modelo enlazó a TextField/DateTimeInput/etc en la tarjeta — a2ui_core
      // ya los resolvió contra el data model en vivo antes de emitir el evento,
      // así que lo que llega aquí es lo que el usuario realmente escribió, no
      // lo que el modelo propuso originalmente.
      const { proposalId, ...context } = action.context ?? {};
      const tieneContext = Object.keys(context).length > 0;
      try {
        const { a2ui_messages } = await confirmAction(proposalId, tieneContext ? context : undefined);
        onMessages([marcarResueltoMessage(action.surfaceId), ...a2ui_messages]);
      } catch (err) {
        onError(err);
      }
      return;
    }
    if (action.name === REJECT_ACTION_NAME) {
      const proposalId = action.context?.proposalId;
      try {
        const { a2ui_messages } = await rejectAction(proposalId);
        onMessages([marcarResueltoMessage(action.surfaceId), ...a2ui_messages]);
      } catch (err) {
        onError(err);
      }
    }
  };
}
