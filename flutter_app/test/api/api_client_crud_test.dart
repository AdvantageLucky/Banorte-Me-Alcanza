// flutter_app/test/api/api_client_crud_test.dart
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:me_alcanza/api/api_client.dart';

class _FakeHttpClient extends http.BaseClient {
  _FakeHttpClient(this.handler);
  final Future<http.StreamedResponse> Function(http.BaseRequest) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => handler(request);
}

http.StreamedResponse _json(int status, Object body) =>
    http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(body))), status);

Map<String, dynamic> _bodyOf(http.BaseRequest r) =>
    jsonDecode((r as http.Request).body) as Map<String, dynamic>;

void main() {
  late http.BaseRequest? captured;
  ApiClient clientReturning(int status, Object body) => ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return _json(status, body);
        }),
      );

  setUp(() => captured = null);

  group('chat con memoria', () {
    test('reenvía conversacion_id cuando se conoce y devuelve el del backend', () async {
      final client = clientReturning(200, {'a2ui_messages': [], 'conversacion_id': 7});
      final turno = await client.sendMessage('jwt', 'hola', conversacionId: 7);
      expect(_bodyOf(captured!), {'mensaje': 'hola', 'conversacion_id': 7});
      expect(turno.conversacionId, 7);
      expect(turno.a2uiMessages, isEmpty);
    });

    test('omite conversacion_id en el primer turno', () async {
      final client = clientReturning(200, {'a2ui_messages': [], 'conversacion_id': 1});
      await client.sendMessage('jwt', 'hola');
      expect(_bodyOf(captured!).containsKey('conversacion_id'), isFalse);
    });
  });

  group('lecturas', () {
    test('getCuenta parsea y enmascara el número', () async {
      final client = clientReturning(200, {
        'titular': 'Ana Torres',
        'numero_cuenta': '001122',
        'saldo': 500,
        'moneda': 'MXN',
      });
      final cuenta = await client.getCuenta('jwt');
      expect(captured!.method, 'GET');
      expect(captured!.url.path, '/api/cuenta');
      expect(captured!.headers['Authorization'], 'Bearer jwt');
      expect(cuenta.saldo, 500.0);
      expect(cuenta.numeroEnmascarado, '····1122');
    });

    test('getGastosFijos usa concepto y getIngresos usa descripcion', () async {
      final gastos = clientReturning(200, [
        {'id': 1, 'concepto': 'Agua', 'monto': 320, 'frecuencia': 'mensual', 'proxima_fecha': '2026-09-15'},
      ]);
      final lista = await gastos.getGastosFijos('jwt');
      expect(lista.single.etiqueta, 'Agua');

      final ingresos = clientReturning(200, [
        {'id': 3, 'descripcion': 'Nómina', 'monto': 12500, 'frecuencia': 'quincenal', 'proxima_fecha': '2026-09-13'},
      ]);
      final lista2 = await ingresos.getIngresos('jwt');
      expect(lista2.single.etiqueta, 'Nómina');
      expect(lista2.single.monto, 12500.0);
    });

    test('getSugerencias conserva la tarjeta A2UI de las pendientes', () async {
      final client = clientReturning(200, [
        {
          'id': 1,
          'tipo': 'gasto_fijo_proximo',
          'entidad_id': '1',
          'detalle': {'concepto': 'Agua', 'monto': 320.0, 'proxima_fecha': '2026-09-15'},
          'estado': 'pendiente',
          'created_at': '2026-09-12 10:00:00',
          'resuelta_at': null,
          'a2ui_json': [
            {'version': 'v0.9', 'createSurface': {'surfaceId': 'sugerencia-abc', 'catalogId': 'x'}},
          ],
        },
        {
          'id': 2,
          'tipo': 'meta_en_riesgo',
          'entidad_id': '7',
          'detalle': {'descripcion': 'Viaje'},
          'estado': 'atendida',
          'created_at': '2026-09-11 10:00:00',
          'resuelta_at': '2026-09-12 09:00:00',
          'a2ui_json': null,
        },
      ]);
      final lista = await client.getSugerencias('jwt');
      expect(lista.first.pendiente, isTrue);
      expect(lista.first.a2uiJson, hasLength(1));
      expect(lista.first.titulo, 'Pago próximo: Agua');
      expect(lista.last.pendiente, isFalse);
      expect(lista.last.a2uiJson, isNull);
      expect(lista.last.titulo, 'Meta en riesgo: Viaje');
    });
  });

  group('escrituras', () {
    test('createGastoFijo manda el payload con snake_case', () async {
      final client = clientReturning(201, {
        'id': 9, 'concepto': 'Renta', 'monto': 4000, 'frecuencia': 'mensual', 'proxima_fecha': '2026-10-01',
      });
      final creado = await client.createGastoFijo('jwt',
          concepto: 'Renta', monto: 4000, frecuencia: 'mensual', proximaFecha: '2026-10-01');
      expect(captured!.method, 'POST');
      expect(_bodyOf(captured!), {
        'concepto': 'Renta', 'monto': 4000, 'frecuencia': 'mensual', 'proxima_fecha': '2026-10-01',
      });
      expect(creado.id, 9);
    });

    test('updateMeta hace PATCH parcial sin mandar nulos', () async {
      final client = clientReturning(200, {
        'id': 1, 'descripcion': 'Concierto', 'monto_objetivo': 9000, 'fecha_objetivo': '2026-10-14', 'monto_ahorrado': 0,
      });
      await client.updateMeta('jwt', 1, montoObjetivo: 9000);
      expect(captured!.method, 'PATCH');
      expect(captured!.url.path, '/api/metas/1');
      expect(_bodyOf(captured!), {'monto_objetivo': 9000});
    });

    test('deleteContacto hace DELETE y acepta 204 sin cuerpo', () async {
      final client = ApiClient(
        'http://api.test',
        httpClient: _FakeHttpClient((request) async {
          captured = request;
          return http.StreamedResponse(const Stream.empty(), 204);
        }),
      );
      await client.deleteContacto('jwt', 5);
      expect(captured!.method, 'DELETE');
      expect(captured!.url.path, '/api/contactos/5');
    });

    test('createApartado y cancelarApartado', () async {
      final client = clientReturning(201, {
        'id': 4, 'meta_id': 1, 'monto_por_periodo': 142.5, 'periodicidad': 'semanal',
        'fecha_inicio': '2026-09-12', 'estado': 'activo',
      });
      final apartado = await client.createApartado('jwt', metaId: 1, montoPorPeriodo: 142.5, periodicidad: 'semanal');
      expect(_bodyOf(captured!), {'meta_id': 1, 'monto_por_periodo': 142.5, 'periodicidad': 'semanal'});
      expect(apartado.activo, isTrue);

      final client2 = clientReturning(200, {
        'id': 4, 'meta_id': 1, 'monto_por_periodo': 142.5, 'periodicidad': 'semanal',
        'fecha_inicio': '2026-09-12', 'estado': 'cancelado',
      });
      final cancelado = await client2.cancelarApartado('jwt', 4);
      expect(captured!.url.path, '/api/apartados/4/cancelar');
      expect(cancelado.activo, isFalse);
    });

    test('atenderSugerencia pega al endpoint correcto', () async {
      final client = clientReturning(200, {
        'id': 1, 'tipo': 'gasto_fijo_proximo', 'entidad_id': '1', 'detalle': {},
        'estado': 'atendida', 'created_at': 'x', 'resuelta_at': 'y', 'a2ui_json': null,
      });
      final s = await client.atenderSugerencia('jwt', 1);
      expect(captured!.url.path, '/api/sugerencias/1/atender');
      expect(s.estado, 'atendida');
    });
  });

  group('errores', () {
    test('un 400 del MCP conserva el mensaje de negocio', () async {
      final client = clientReturning(400, {'detail': 'Saldo insuficiente para el primer periodo del apartado'});
      await expectLater(
        client.createApartado('jwt', metaId: 1, montoPorPeriodo: 99999, periodicidad: 'semanal'),
        throwsA(isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 400)
            .having((e) => e.detail, 'detail', 'Saldo insuficiente para el primer periodo del apartado')),
      );
    });

    test('un 422 de validación junta los msg en un solo texto', () async {
      final client = clientReturning(422, {
        'detail': [
          {'loc': ['body', 'monto'], 'msg': 'Input should be greater than 0', 'type': 'greater_than'},
        ],
      });
      await expectLater(
        client.createGastoFijo('jwt', concepto: 'x', monto: -1, frecuencia: 'mensual', proximaFecha: '2026-10-01'),
        throwsA(isA<ApiException>().having((e) => e.detail, 'detail', 'Input should be greater than 0')),
      );
    });
  });
}
