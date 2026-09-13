// flutter_app/test/api/api_client_test.dart
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:me_alcanza/api/api_client.dart';

class _FakeHttpClient extends http.BaseClient {
  _FakeHttpClient(this.handler);
  final Future<http.StreamedResponse> Function(http.BaseRequest) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) =>
      handler(request);
}

http.StreamedResponse _jsonResponse(int statusCode, Map<String, dynamic> body) {
  final bytes = utf8.encode(jsonEncode(body));
  return http.StreamedResponse(Stream.value(bytes), statusCode);
}

void main() {
  group('ApiClient', () {
    test('posts credentials to /api/login and returns the token', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'token': 'jwt-123'});
        }),
      );

      final token = await client.login('ana', 'pass123');

      expect(token, 'jwt-123');
      expect(captured!.url.toString(), 'http://api.test/api/login');
      expect(captured!.method, 'POST');
      expect(captured!.headers['Content-Type'], 'application/json');
      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'username': 'ana', 'password': 'pass123'});
    });

    test('sends the bearer token and mensaje on /api/chat', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.sendMessage('jwt-123', '¿me alcanza para el concierto?');

      expect(captured!.headers['Authorization'], 'Bearer jwt-123');
      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'mensaje': '¿me alcanza para el concierto?'});
    });

    test('sends proposal_id on /api/confirm-action', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.confirmAction('jwt-123', 'prop-1');

      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'proposal_id': 'prop-1', 'context': null});
    });

    test('sends the edited fields as context on /api/confirm-action when provided', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.confirmAction('jwt-123', 'prop-1', {'nombre': 'Mamá'});

      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'proposal_id': 'prop-1', 'context': {'nombre': 'Mamá'}});
    });

    test('sends proposal_id on /api/reject-action', () async {
      http.BaseRequest? captured;
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _jsonResponse(200, {'a2ui_messages': []});
        }),
      );

      await client.rejectAction('jwt-123', 'prop-1');

      final sentBody =
          jsonDecode((captured! as http.Request).body) as Map<String, dynamic>;
      expect(sentBody, {'proposal_id': 'prop-1'});
    });

    test('throws an ApiException carrying the backend detail on a non-2xx response',
        () async {
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          return _jsonResponse(401, {'detail': 'Usuario o contraseña incorrectos'});
        }),
      );

      await expectLater(
        client.login('ana', 'wrong'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.detail, 'detail', 'Usuario o contraseña incorrectos'),
        ),
      );
    });

    test('falls back to a null detail when the error body is not JSON', () async {
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          final bytes = utf8.encode('not json');
          return http.StreamedResponse(Stream.value(bytes), 500);
        }),
      );

      await expectLater(client.login('ana', 'x'), throwsA(isA<ApiException>()));
    });
  });
}
