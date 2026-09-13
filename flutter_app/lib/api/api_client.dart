// flutter_app/lib/api/api_client.dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.detail);

  final int statusCode;
  final String? detail;

  @override
  String toString() => detail ?? 'Error HTTP $statusCode';
}

/// Cliente REST del backend. Una función por endpoint; los errores de
/// regla de negocio del MCP llegan como `ApiException(400, detalle)` con
/// el mensaje original, así que la UI puede mostrarlos tal cual.
class ApiClient {
  ApiClient(this.baseUrl, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  final String baseUrl;
  final http.Client _http;

  // ---------------------------------------------------------------- auth

  Future<String> login(String username, String password) async {
    final body = await _post('/api/login', body: {
      'username': username,
      'password': password,
    });
    return body['token'] as String;
  }

  // ---------------------------------------------------------------- chat

  /// Envía un mensaje al asistente. Sin [conversacionId] el backend abre
  /// un hilo nuevo y lo devuelve; la pantalla debe reenviarlo en el
  /// siguiente turno para conservar la memoria.
  Future<ChatTurnResponse> sendMessage(
    String token,
    String mensaje, {
    int? conversacionId,
  }) async {
    final body = await _post(
      '/api/chat',
      body: {
        'mensaje': mensaje,
        'conversacion_id': ?conversacionId,
      },
      token: token,
    );
    return ChatTurnResponse(
      a2uiMessages: body['a2ui_messages'] as List<dynamic>,
      conversacionId: body['conversacion_id'] as int?,
    );
  }

  Future<List<dynamic>> confirmAction(
    String token,
    String proposalId, [
    Map<String, dynamic>? context,
  ]) async {
    final body = await _post(
      '/api/confirm-action',
      body: {'proposal_id': proposalId, 'context': context},
      token: token,
    );
    return body['a2ui_messages'] as List<dynamic>;
  }

  // ------------------------------------------------------- conversaciones

  Future<List<Conversacion>> getConversaciones(String token) async =>
      _list(await _getList('/api/conversaciones', token: token), Conversacion.fromJson);

  Future<List<MensajeConversacion>> getMensajesConversacion(String token, int id) async => _list(
        await _getList('/api/conversaciones/$id/mensajes', token: token),
        MensajeConversacion.fromJson,
      );

  Future<void> eliminarConversacion(String token, int id) =>
      _delete('/api/conversaciones/$id', token: token);

  // -------------------------------------------------------------- cuenta

  Future<Cuenta> getCuenta(String token) async =>
      Cuenta.fromJson(await _get('/api/cuenta', token: token));

  Future<List<Movimiento>> getMovimientos(String token, {int limit = 20}) async =>
      _list(await _getList('/api/movimientos?limit=$limit', token: token), Movimiento.fromJson);

  Future<ScoreSalud> getScoreSalud(String token) async =>
      ScoreSalud.fromJson(await _get('/api/score-salud-financiera', token: token));

  // ----------------------------------------------------------- contactos

  Future<List<Contacto>> getContactos(String token) async =>
      _list(await _getList('/api/contactos', token: token), Contacto.fromJson);

  Future<Contacto> createContacto(
    String token, {
    required String nombre,
    required String alias,
    required String cuentaDestino,
    required String relacion,
  }) async =>
      Contacto.fromJson(await _post('/api/contactos', token: token, body: {
        'nombre': nombre,
        'alias': alias,
        'cuenta_destino': cuentaDestino,
        'relacion': relacion,
      }));

  Future<Contacto> updateContacto(
    String token,
    int id, {
    String? nombre,
    String? alias,
    String? cuentaDestino,
    String? relacion,
  }) async =>
      Contacto.fromJson(await _patch('/api/contactos/$id', token: token, body: {
        'nombre': ?nombre,
        'alias': ?alias,
        'cuenta_destino': ?cuentaDestino,
        'relacion': ?relacion,
      }));

  Future<void> deleteContacto(String token, int id) =>
      _delete('/api/contactos/$id', token: token);

  // --------------------------------------------------- ingresos programados

  Future<List<Recurrente>> getIngresos(String token) async =>
      _list(await _getList('/api/ingresos-programados', token: token), Recurrente.ingreso);

  Future<Recurrente> createIngreso(
    String token, {
    required String descripcion,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) async =>
      Recurrente.ingreso(await _post('/api/ingresos-programados', token: token, body: {
        'descripcion': descripcion,
        'monto': monto,
        'frecuencia': frecuencia,
        'proxima_fecha': proximaFecha,
      }));

  Future<Recurrente> updateIngreso(
    String token,
    int id, {
    String? descripcion,
    double? monto,
    String? frecuencia,
    String? proximaFecha,
  }) async =>
      Recurrente.ingreso(await _patch('/api/ingresos-programados/$id', token: token, body: {
        'descripcion': ?descripcion,
        'monto': ?monto,
        'frecuencia': ?frecuencia,
        'proxima_fecha': ?proximaFecha,
      }));

  Future<void> deleteIngreso(String token, int id) =>
      _delete('/api/ingresos-programados/$id', token: token);

  // --------------------------------------------------------- gastos fijos

  Future<List<Recurrente>> getGastosFijos(String token) async =>
      _list(await _getList('/api/gastos-fijos', token: token), Recurrente.gastoFijo);

  Future<Recurrente> createGastoFijo(
    String token, {
    required String concepto,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) async =>
      Recurrente.gastoFijo(await _post('/api/gastos-fijos', token: token, body: {
        'concepto': concepto,
        'monto': monto,
        'frecuencia': frecuencia,
        'proxima_fecha': proximaFecha,
      }));

  Future<Recurrente> updateGastoFijo(
    String token,
    int id, {
    String? concepto,
    double? monto,
    String? frecuencia,
    String? proximaFecha,
  }) async =>
      Recurrente.gastoFijo(await _patch('/api/gastos-fijos/$id', token: token, body: {
        'concepto': ?concepto,
        'monto': ?monto,
        'frecuencia': ?frecuencia,
        'proxima_fecha': ?proximaFecha,
      }));

  Future<void> deleteGastoFijo(String token, int id) =>
      _delete('/api/gastos-fijos/$id', token: token);

  // ---------------------------------------------------------------- metas

  Future<List<Meta>> getMetas(String token) async =>
      _list(await _getList('/api/metas', token: token), Meta.fromJson);

  Future<Meta> createMeta(
    String token, {
    required String descripcion,
    required double montoObjetivo,
    required String fechaObjetivo,
  }) async =>
      Meta.fromJson(await _post('/api/metas', token: token, body: {
        'descripcion': descripcion,
        'monto_objetivo': montoObjetivo,
        'fecha_objetivo': fechaObjetivo,
      }));

  Future<Meta> updateMeta(
    String token,
    int id, {
    String? descripcion,
    double? montoObjetivo,
    String? fechaObjetivo,
  }) async =>
      Meta.fromJson(await _patch('/api/metas/$id', token: token, body: {
        'descripcion': ?descripcion,
        'monto_objetivo': ?montoObjetivo,
        'fecha_objetivo': ?fechaObjetivo,
      }));

  Future<void> deleteMeta(String token, int id) => _delete('/api/metas/$id', token: token);

  // ------------------------------------------------------------ apartados

  Future<List<Apartado>> getApartados(String token) async =>
      _list(await _getList('/api/apartados', token: token), Apartado.fromJson);

  Future<Apartado> createApartado(
    String token, {
    required int metaId,
    required double montoPorPeriodo,
    required String periodicidad,
  }) async =>
      Apartado.fromJson(await _post('/api/apartados', token: token, body: {
        'meta_id': metaId,
        'monto_por_periodo': montoPorPeriodo,
        'periodicidad': periodicidad,
      }));

  Future<Apartado> cancelarApartado(String token, int id) async =>
      Apartado.fromJson(await _post('/api/apartados/$id/cancelar', token: token, body: const {}));

  // ---------------------------------------------------------- sugerencias

  /// Genera (deduplicando) y devuelve todas las sugerencias de la cuenta,
  /// pendientes e históricas. Las pendientes traen su tarjeta A2UI.
  Future<List<Sugerencia>> getSugerencias(String token) async =>
      _list(await _getList('/api/sugerencias', token: token), Sugerencia.fromJson);

  Future<Sugerencia> atenderSugerencia(String token, int id) async =>
      Sugerencia.fromJson(await _post('/api/sugerencias/$id/atender', token: token, body: const {}));

  Future<Sugerencia> descartarSugerencia(String token, int id) async =>
      Sugerencia.fromJson(await _post('/api/sugerencias/$id/descartar', token: token, body: const {}));

  // ------------------------------------------------------------ plomería

  static List<T> _list<T>(List<dynamic> raw, T Function(Map<String, dynamic>) parse) =>
      raw.map((e) => parse((e as Map).cast<String, dynamic>())).toList();

  Map<String, String> _headers(String? token) => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<Map<String, dynamic>> _get(String path, {required String token}) async {
    final response = await _http.get(Uri.parse('$baseUrl$path'), headers: _headers(token));
    return _decodeObject(response);
  }

  Future<List<dynamic>> _getList(String path, {required String token}) async {
    final response = await _http.get(Uri.parse('$baseUrl$path'), headers: _headers(token));
    _throwIfError(response);
    return jsonDecode(utf8.decode(response.bodyBytes)) as List<dynamic>;
  }

  Future<Map<String, dynamic>> _post(
    String path, {
    required Map<String, dynamic> body,
    String? token,
  }) async {
    final response = await _http.post(
      Uri.parse('$baseUrl$path'),
      headers: _headers(token),
      body: jsonEncode(body),
    );
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> _patch(
    String path, {
    required Map<String, dynamic> body,
    required String token,
  }) async {
    final response = await _http.patch(
      Uri.parse('$baseUrl$path'),
      headers: _headers(token),
      body: jsonEncode(body),
    );
    return _decodeObject(response);
  }

  Future<void> _delete(String path, {required String token}) async {
    final response = await _http.delete(Uri.parse('$baseUrl$path'), headers: _headers(token));
    _throwIfError(response);
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    _throwIfError(response);
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  void _throwIfError(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    String? detail;
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      // FastAPI manda `detail` como string en errores de negocio y como
      // lista de objetos en errores de validación (422).
      if (decoded is Map && decoded['detail'] is String) {
        detail = decoded['detail'] as String;
      } else if (decoded is Map && decoded['detail'] is List) {
        final errores = decoded['detail'] as List;
        detail = errores.map((e) => (e as Map)['msg']).whereType<String>().join('. ');
        if (detail.isEmpty) detail = null;
      }
    } catch (_) {
      detail = null;
    }
    throw ApiException(response.statusCode, detail);
  }
}
