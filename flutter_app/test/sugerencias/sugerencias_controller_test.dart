// flutter_app/test/sugerencias/sugerencias_controller_test.dart
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:me_alcanza/api/api_client.dart';
import 'package:me_alcanza/sugerencias/sugerencias_controller.dart';

class _FakeHttpClient extends http.BaseClient {
  _FakeHttpClient(this.handler);
  final Future<http.StreamedResponse> Function(http.BaseRequest) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => handler(request);
}

http.StreamedResponse _json(int status, Object body) =>
    http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(body))), status);

Map<String, dynamic> _sug(int id, String estado) => {
      'id': id,
      'tipo': 'gasto_fijo_proximo',
      'entidad_id': '$id',
      'detalle': {'concepto': 'Agua', 'monto': 320.0, 'proxima_fecha': '2026-09-15'},
      'estado': estado,
      'created_at': '2026-09-12 10:00:00',
      'resuelta_at': estado == 'pendiente' ? null : '2026-09-12 11:00:00',
      'a2ui_json': estado == 'pendiente'
          ? [
              {'version': 'v0.9', 'createSurface': {'surfaceId': 'sugerencia-$id', 'catalogId': 'c'}},
            ]
          : null,
    };

void main() {
  test('cargar separa pendientes de historial y cuenta pendientes', () async {
    final client = ApiClient(
      'http://api.test',
      httpClient: _FakeHttpClient((r) async => _json(200, [_sug(1, 'pendiente'), _sug(2, 'atendida'), _sug(3, 'pendiente')])),
    );
    final controller = SugerenciasController(apiClient: client, tokenProvider: () => 'jwt');
    var notificaciones = 0;
    controller.addListener(() => notificaciones++);

    await controller.cargar();

    expect(controller.primeraCargaHecha, isTrue);
    expect(controller.pendientesCount, 2);
    expect(controller.pendientes.map((s) => s.id), [1, 3]);
    expect(controller.historial.single.id, 2);
    expect(controller.error, isNull);
    expect(notificaciones, greaterThanOrEqualTo(2), reason: 'al empezar y al terminar');
  });

  test('atender reemplaza la sugerencia en sitio y la saca de pendientes', () async {
    final client = ApiClient(
      'http://api.test',
      httpClient: _FakeHttpClient((r) async {
        if (r.url.path == '/api/sugerencias') return _json(200, [_sug(1, 'pendiente'), _sug(2, 'pendiente')]);
        if (r.url.path == '/api/sugerencias/1/atender') return _json(200, _sug(1, 'atendida'));
        return _json(404, {'detail': 'no'});
      }),
    );
    final controller = SugerenciasController(apiClient: client, tokenProvider: () => 'jwt');
    await controller.cargar();

    final actualizada = await controller.atender(1);

    expect(actualizada.estado, 'atendida');
    expect(controller.pendientesCount, 1);
    expect(controller.pendientes.single.id, 2);
    expect(controller.historial.single.id, 1);
  });

  test('un fallo de red deja el error y no rompe el estado previo', () async {
    var llamadas = 0;
    final client = ApiClient(
      'http://api.test',
      httpClient: _FakeHttpClient((r) async {
        llamadas++;
        if (llamadas == 1) return _json(200, [_sug(1, 'pendiente')]);
        return _json(503, {'detail': 'caído'});
      }),
    );
    final controller = SugerenciasController(apiClient: client, tokenProvider: () => 'jwt');
    await controller.cargar();
    expect(controller.pendientesCount, 1);

    await controller.cargar();

    expect(controller.error, isA<ApiException>());
    expect(controller.pendientesCount, 1, reason: 'conserva lo último bueno');
    expect(controller.cargando, isFalse);
  });
}
