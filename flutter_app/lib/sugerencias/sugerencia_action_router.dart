// flutter_app/lib/sugerencias/sugerencia_action_router.dart
//
// Enruta las acciones de las tarjetas A2UI de sugerencias (armadas por el
// backend en sugerencias_a2ui.py) a los endpoints REST correspondientes.
// Puro: sin Flutter, sin HTTP directo, para poder probarlo solo.
import '../models/models.dart';

const atenderActionName = 'atender_sugerencia';
const descartarActionName = 'descartar_sugerencia';

typedef MarcarSugerenciaFn = Future<Sugerencia> Function(int sugerenciaId);
typedef OnSugerenciaResueltaFn = void Function(Sugerencia sugerencia);
typedef OnErrorFn = void Function(Object error);

/// Antes de ejecutar `atender`, le pide al llamador que confirme con el
/// usuario (modal HITL) — espejo de requestConfirmacion en
/// sugerenciaActionHandler.js. `onConfirm` ejecuta la acción real; si el
/// usuario cancela, el llamador simplemente no lo invoca.
typedef RequestConfirmacionFn = Future<void> Function(
  int sugerenciaId,
  Future<void> Function() onConfirm,
);

class SugerenciaActionRouter {
  SugerenciaActionRouter({
    required this.atender,
    required this.descartar,
    required this.requestConfirmacion,
    required this.onResuelta,
    required this.onError,
  });

  final MarcarSugerenciaFn atender;
  final MarcarSugerenciaFn descartar;
  final RequestConfirmacionFn requestConfirmacion;
  final OnSugerenciaResueltaFn onResuelta;
  final OnErrorFn onError;

  /// Devuelve `true` si la acción era de sugerencias (aunque fallara).
  Future<bool> handle(Map<String, dynamic> action) async {
    final name = action['name'];
    if (name != atenderActionName && name != descartarActionName) return false;

    final context = (action['context'] as Map?)?.cast<String, dynamic>();
    final rawId = context?['sugerenciaId'];
    final id = switch (rawId) {
      int v => v,
      String v => int.tryParse(v),
      _ => null,
    };
    if (id == null) return true;

    // Descartar es de bajo riesgo (solo cambia el estado, no mueve dinero
    // ni crea nada): se ejecuta directo. Atender sí dispara una acción
    // sobre la que vale la pena pedir foco humano, igual que
    // confirmar_accion.
    if (name == descartarActionName) {
      try {
        onResuelta(await descartar(id));
      } catch (err) {
        onError(err);
      }
      return true;
    }

    await requestConfirmacion(id, () async {
      try {
        onResuelta(await atender(id));
      } catch (err) {
        onError(err);
      }
    });
    return true;
  }
}
