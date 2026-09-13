export const ATENDER_SUGERENCIA_NAME = 'atender_sugerencia';
export const DESCARTAR_SUGERENCIA_NAME = 'descartar_sugerencia';

// Descartar es de bajo riesgo (solo cambia el estado de la sugerencia, no
// mueve dinero ni crea nada) y se ejecuta directo. Atender sí dispara una
// acción sobre la que vale la pena pedir foco humano — igual que
// confirmar_accion, pasa por un modal nativo (requestConfirmacion) antes de
// ejecutarse; quien llama a este handler decide qué mostrar en ese modal
// (título/descripción ya conocidos del lado del cliente, más una propuesta
// del LLM cargada bajo demanda si la hay).
export function createSugerenciaActionHandler({
  atenderSugerencia,
  descartarSugerencia,
  requestConfirmacion,
  onResuelta,
  onError,
}) {
  return async function handleAction(action) {
    const sugerenciaId = action.context?.sugerenciaId;

    if (action.name === DESCARTAR_SUGERENCIA_NAME) {
      try {
        await descartarSugerencia(sugerenciaId);
        onResuelta(sugerenciaId);
      } catch (err) {
        onError(err);
      }
      return;
    }

    if (action.name === ATENDER_SUGERENCIA_NAME) {
      requestConfirmacion({
        sugerenciaId,
        onConfirm: async () => {
          try {
            await atenderSugerencia(sugerenciaId);
            onResuelta(sugerenciaId);
          } catch (err) {
            onError(err);
          }
        },
        onCancel: () => {},
      });
    }
  };
}
