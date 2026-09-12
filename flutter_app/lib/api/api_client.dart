// flutter_app/lib/api/api_client.dart
import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.statusCode, this.detail);

  final int statusCode;
  final String? detail;

  @override
  String toString() => detail ?? 'Error HTTP $statusCode';
}

class ApiClient {
  ApiClient(this.baseUrl, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  final String baseUrl;
  final http.Client _http;

  Future<String> login(String username, String password) async {
    final body = await _post('/api/login', body: {
      'username': username,
      'password': password,
    });
    return body['token'] as String;
  }

  Future<List<dynamic>> sendMessage(String token, String mensaje) async {
    final body = await _post(
      '/api/chat',
      body: {'mensaje': mensaje},
      token: token,
    );
    return body['a2ui_messages'] as List<dynamic>;
  }

  Future<List<dynamic>> confirmAction(String token, String proposalId) async {
    final body = await _post(
      '/api/confirm-action',
      body: {'proposal_id': proposalId},
      token: token,
    );
    return body['a2ui_messages'] as List<dynamic>;
  }

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
    String? token,
  }) async {
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final response = await _http.post(
      Uri.parse('$baseUrl$path'),
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String? detail;
      try {
        final bodyString = utf8.decode(response.bodyBytes);
        final decoded = jsonDecode(bodyString) as Map<String, dynamic>;
        detail = decoded['detail'] as String?;
      } catch (_) {
        detail = null;
      }
      throw ApiException(response.statusCode, detail);
    }
    final bodyString = utf8.decode(response.bodyBytes);
    return jsonDecode(bodyString) as Map<String, dynamic>;
  }
}
