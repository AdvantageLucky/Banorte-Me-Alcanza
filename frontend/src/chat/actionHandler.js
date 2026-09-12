export const CONFIRM_ACTION_NAME = 'confirmar_accion';

export function createActionHandler({ confirmAction, onMessages, onError }) {
  return async function handleAction(action) {
    if (action.name !== CONFIRM_ACTION_NAME) {
      return;
    }
    const proposalId = action.context?.proposalId;
    try {
      const { a2ui_messages } = await confirmAction(proposalId);
      onMessages(a2ui_messages);
    } catch (err) {
      onError(err);
    }
  };
}
