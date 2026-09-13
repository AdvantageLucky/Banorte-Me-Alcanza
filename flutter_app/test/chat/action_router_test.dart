// flutter_app/test/chat/action_router_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/chat/action_router.dart';

void main() {
  group('ActionRouter', () {
    test('ignores actions with a name other than confirmar_accion', () async {
      var confirmCalled = false;
      var messagesCalled = false;
      var errorCalled = false;
      final router = ActionRouter(
        confirmAction: (id, context) async {
          confirmCalled = true;
          return [];
        },
        onMessages: (_) => messagesCalled = true,
        onError: (_) => errorCalled = true,
      );

      await router.handle({
        'name': 'otra_accion',
        'context': {'proposalId': 'prop-1'},
      });

      expect(confirmCalled, isFalse);
      expect(messagesCalled, isFalse);
      expect(errorCalled, isFalse);
    });

    test(
        'confirms the proposal from context.proposalId and forwards the resulting messages',
        () async {
      String? receivedId;
      Map<String, dynamic>? receivedContext;
      List<dynamic>? receivedMessages;
      final router = ActionRouter(
        confirmAction: (id, context) async {
          receivedId = id;
          receivedContext = context;
          return [
            {'foo': 'bar'}
          ];
        },
        onMessages: (messages) => receivedMessages = messages,
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedId, 'prop-1');
      expect(receivedContext, isNull);
      expect(receivedMessages, [
        {'foo': 'bar'}
      ]);
    });

    test('forwards any edited fields alongside proposalId as a separate context argument',
        () async {
      Map<String, dynamic>? receivedContext;
      final router = ActionRouter(
        confirmAction: (id, context) async {
          receivedContext = context;
          return [];
        },
        onMessages: (_) {},
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'context': {
          'proposalId': 'prop-1',
          'nombre': 'Mamá',
          'cuenta_destino': '1234567890',
        },
      });

      expect(receivedContext, {'nombre': 'Mamá', 'cuenta_destino': '1234567890'});
    });

    test('reports an error when confirming the proposal fails, without touching onMessages',
        () async {
      final failure = Exception('boom');
      Object? receivedError;
      final router = ActionRouter(
        confirmAction: (id, context) async => throw failure,
        onMessages: (_) => fail('should not be called'),
        onError: (err) => receivedError = err,
      );

      await router.handle({
        'name': confirmActionName,
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedError, failure);
    });

    test('does nothing when proposalId is missing from context', () async {
      var confirmCalled = false;
      final router = ActionRouter(
        confirmAction: (id, context) async {
          confirmCalled = true;
          return [];
        },
        onMessages: (_) {},
        onError: (_) => fail('should not be called'),
      );

      await router.handle({'name': confirmActionName, 'context': <String, dynamic>{}});

      expect(confirmCalled, isFalse);
    });
  });
}
