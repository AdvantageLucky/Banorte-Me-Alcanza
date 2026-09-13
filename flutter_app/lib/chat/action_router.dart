const confirmActionName = 'confirmar_accion';
const rejectActionName = 'rechazar_accion';

typedef ConfirmActionFn = Future<List<dynamic>> Function(
  String proposalId,
  Map<String, dynamic>? context,
);
typedef RejectActionFn = Future<List<dynamic>> Function(String proposalId);
typedef OnMessagesFn = void Function(List<dynamic> messages);
typedef OnErrorFn = void Function(Object error);

// Marca la tarjeta ORIGINAL (no el mensaje nuevo de resultado) como resuelta,
// escribiendo directo al path que el system prompt instruye a inicializar en
// cada tarjeta de confirmación ('/resuelto'). El Button de esa tarjeta trae
// un `checks` que lo deshabilita cuando ese path es true — así el botón deja
// de verse activo para siempre después de que la propuesta ya se usó, sin
// tener que rastrear estado aparte del propio data model de a2ui.
Map<String, dynamic> _marcarResueltoMessage(String surfaceId) => {
  'version': 'v0.9',
  'updateDataModel': {
    'surfaceId': surfaceId,
    'path': '/resuelto',
    'value': true,
  },
};

class ActionRouter {
  ActionRouter({
    required this.confirmAction,
    required this.rejectAction,
    required this.onMessages,
    required this.onError,
  });

  final ConfirmActionFn confirmAction;
  final RejectActionFn rejectAction;
  final OnMessagesFn onMessages;
  final OnErrorFn onError;

  Future<void> handle(Map<String, dynamic> action) async {
    final name = action['name'];
    if (name != confirmActionName && name != rejectActionName) {
      return;
    }
    final actionContext = action['context'] as Map<String, dynamic>?;
    final proposalId = actionContext?['proposalId'] as String?;
    if (proposalId == null) {
      return;
    }
    final surfaceId = action['surfaceId'] as String?;
    try {
      final List<dynamic> messages;
      if (name == confirmActionName) {
        // El resto de actionContext (además de proposalId) son los campos
        // que el modelo enlazó a un TextField/DateTimeInput/etc en la
        // tarjeta — genui ya los resolvió contra el data model en vivo antes
        // de dispatchEvent, así que esto es lo que el usuario realmente
        // escribió, no lo que el modelo propuso originalmente.
        final editedContext = Map<String, dynamic>.from(actionContext ?? {})
          ..remove('proposalId');
        messages = await confirmAction(
          proposalId,
          editedContext.isEmpty ? null : editedContext,
        );
      } else {
        messages = await rejectAction(proposalId);
      }
      onMessages([
        if (surfaceId != null) _marcarResueltoMessage(surfaceId),
        ...messages,
      ]);
    } catch (err) {
      onError(err);
    }
  }
}
