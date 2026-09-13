// flutter_app/test/chat/action_router_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/chat/action_router.dart';

const _resueltoMessage = {
  'version': 'v0.9',
  'updateDataModel': {'surfaceId': 'main', 'path': '/resuelto', 'value': true},
};

void main() {
  group('ActionRouter', () {
    test('ignores actions with a name other than confirmar_accion or rechazar_accion', () async {
      var confirmCalled = false;
      var rejectCalled = false;
      var messagesCalled = false;
      var errorCalled = false;
      final router = ActionRouter(
        confirmAction: (id, context) async {
          confirmCalled = true;
          return [];
        },
        rejectAction: (id) async {
          rejectCalled = true;
          return [];
        },
        onMessages: (_) => messagesCalled = true,
        onError: (_) => errorCalled = true,
      );

      await router.handle({
        'name': 'otra_accion',
        'surfaceId': 'main',
        'context': {'proposalId': 'prop-1'},
      });

      expect(confirmCalled, isFalse);
      expect(rejectCalled, isFalse);
      expect(messagesCalled, isFalse);
      expect(errorCalled, isFalse);
    });

    test(
        'confirms the proposal from context.proposalId and marks the original surface as resuelta',
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
        rejectAction: (id) async => [],
        onMessages: (messages) => receivedMessages = messages,
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'surfaceId': 'main',
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedId, 'prop-1');
      expect(receivedContext, isNull);
      expect(receivedMessages, [
        _resueltoMessage,
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
        rejectAction: (id) async => [],
        onMessages: (_) {},
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'surfaceId': 'main',
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
        rejectAction: (id) async => [],
        onMessages: (_) => fail('should not be called'),
        onError: (err) => receivedError = err,
      );

      await router.handle({
        'name': confirmActionName,
        'surfaceId': 'main',
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
        rejectAction: (id) async => [],
        onMessages: (_) {},
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': confirmActionName,
        'surfaceId': 'main',
        'context': <String, dynamic>{},
      });

      expect(confirmCalled, isFalse);
    });

    test('rejects the proposal from context.proposalId and marks the original surface as resuelta',
        () async {
      String? receivedId;
      List<dynamic>? receivedMessages;
      final router = ActionRouter(
        confirmAction: (id, context) async => [],
        rejectAction: (id) async {
          receivedId = id;
          return [
            {'foo': 'cancelado'}
          ];
        },
        onMessages: (messages) => receivedMessages = messages,
        onError: (_) => fail('should not be called'),
      );

      await router.handle({
        'name': rejectActionName,
        'surfaceId': 'main',
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedId, 'prop-1');
      expect(receivedMessages, [
        _resueltoMessage,
        {'foo': 'cancelado'}
      ]);
    });

    test('reports an error when rejecting the proposal fails, without touching onMessages',
        () async {
      final failure = Exception('boom');
      Object? receivedError;
      final router = ActionRouter(
        confirmAction: (id, context) async => [],
        rejectAction: (id) async => throw failure,
        onMessages: (_) => fail('should not be called'),
        onError: (err) => receivedError = err,
      );

      await router.handle({
        'name': rejectActionName,
        'surfaceId': 'main',
        'context': {'proposalId': 'prop-1'},
      });

      expect(receivedError, failure);
    });
  });
}
