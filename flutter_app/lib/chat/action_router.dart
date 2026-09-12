const confirmActionName = 'confirmar_accion';

typedef ConfirmActionFn = Future<List<dynamic>> Function(String proposalId);
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
    final context = action['context'] as Map<String, dynamic>?;
    final proposalId = context?['proposalId'] as String?;
    if (proposalId == null) {
      return;
    }
    try {
      final messages = await confirmAction(proposalId);
      onMessages(messages);
    } catch (err) {
      onError(err);
    }
  }
}
