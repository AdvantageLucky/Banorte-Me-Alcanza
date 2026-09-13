export const ATENDER_SUGERENCIA_NAME = 'atender_sugerencia';
export const DESCARTAR_SUGERENCIA_NAME = 'descartar_sugerencia';

// Igual que actionHandler.js (confirmar_accion), pero para los botones de las
// tarjetas de notificación: atender/descartar solo cambian el estado de la
// sugerencia (no mueven dinero ni crean nada), así que no pasan por el modal
// de confirmación — se ejecutan directo y el turno de la tarjeta desaparece
// del feed cuando resuelven.
export function createSugerenciaActionHandler({ atenderSugerencia, descartarSugerencia, onResuelta, onError }) {
  return async function handleAction(action) {
    if (action.name !== ATENDER_SUGERENCIA_NAME && action.name !== DESCARTAR_SUGERENCIA_NAME) {
      return;
    }
    const sugerenciaId = action.context?.sugerenciaId;
    try {
      const llamada = action.name === ATENDER_SUGERENCIA_NAME ? atenderSugerencia : descartarSugerencia;
      await llamada(sugerenciaId);
      onResuelta(sugerenciaId);
    } catch (err) {
      onError(err);
    }
  };
}
