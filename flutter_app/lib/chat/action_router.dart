const confirmActionName = 'confirmar_accion';

typedef ConfirmActionFn = Future<List<dynamic>> Function(
  String proposalId,
  Map<String, dynamic>? context,
);
typedef OnMessagesFn = void Function(List<dynamic> messages);
typedef OnErrorFn = void Function(Object error);

class ActionRouter {
  ActionRouter({
    required this.confirmAction,
    required this.onMessages,
    required this.onError,
  });

  final ConfirmActionFn confirmAction;
  final OnMessagesFn onMessages;
  final OnErrorFn onError;

  Future<void> handle(Map<String, dynamic> action) async {
    if (action['name'] != confirmActionName) {
      return;
    }
    final actionContext = action['context'] as Map<String, dynamic>?;
    final proposalId = actionContext?['proposalId'] as String?;
    if (proposalId == null) {
      return;
    }
    // El resto de actionContext (además de proposalId) son los campos que el
    // modelo enlazó a un TextField/DateTimeInput/etc en la tarjeta — genui ya
    // los resolvió contra el data model en vivo antes de dispatchEvent, así
    // que esto es lo que el usuario realmente escribió, no lo que el modelo
    // propuso originalmente.
    final editedContext = Map<String, dynamic>.from(actionContext ?? {})
      ..remove('proposalId');
    try {
      final messages = await confirmAction(
        proposalId,
        editedContext.isEmpty ? null : editedContext,
      );
      onMessages(messages);
    } catch (err) {
      onError(err);
    }
  }
}
