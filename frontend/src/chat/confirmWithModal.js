// Envuelve la confirmación de una propuesta (transferencia, apartado, etc.)
// para que, antes de ejecutar la acción real, el usuario vea un resumen que
// construyó el backend con datos ya validados (getPropuesta) — nunca el
// texto que el LLM escribió en la tarjeta A2UI — y confirme explícitamente
// en un modal ajeno a A2UI (requestConfirmation). Cancelar rechaza con un
// error "silencioso" (err.silent === true) para que el llamador no lo trate
// como una falla real.
export function createConfirmActionWithModal({ getPropuesta, confirmAction, requestConfirmation }) {
  return async function confirmActionWithModal(proposalId, context) {
    const { resumen } = await getPropuesta(proposalId);
    return new Promise((resolve, reject) => {
      requestConfirmation({
        resumen,
        onConfirm: async () => {
          try {
            resolve(await confirmAction(proposalId, context));
          } catch (err) {
            reject(err);
          }
        },
        onCancel: () => {
          const cancelado = new Error('Cancelado por el usuario');
          cancelado.silent = true;
          reject(cancelado);
        },
      });
    });
  };
}
