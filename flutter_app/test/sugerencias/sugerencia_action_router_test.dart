// flutter_app/test/sugerencias/sugerencia_action_router_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/models/models.dart';
import 'package:me_alcanza/sugerencias/sugerencia_action_router.dart';

Sugerencia _sugerencia(int id, String estado) => Sugerencia(
      id: id,
      tipo: 'gasto_fijo_proximo',
      entidadId: '1',
      detalle: const {'concepto': 'Agua'},
      estado: estado,
      createdAt: 'x',
      resueltaAt: estado == 'pendiente' ? null : 'y',
      a2uiJson: null,
    );

void main() {
  test('ignora acciones que no son de sugerencias', () async {
    var llamado = false;
    final router = SugerenciaActionRouter(
      atender: (_) async { llamado = true; return _sugerencia(1, 'atendida'); },
      descartar: (_) async { llamado = true; return _sugerencia(1, 'descartada'); },
      onResuelta: (_) => llamado = true,
      onError: (_) => llamado = true,
    );
    final manejada = await router.handle({'name': 'confirmar_accion', 'context': {'proposalId': 'p'}});
    expect(manejada, isFalse);
    expect(llamado, isFalse);
  });

  test('atender_sugerencia llama a atender con el id del contexto', () async {
    int? recibido;
    Sugerencia? resuelta;
    final router = SugerenciaActionRouter(
      atender: (id) async { recibido = id; return _sugerencia(id, 'atendida'); },
      descartar: (_) async => throw StateError('no debía descartar'),
      onResuelta: (s) => resuelta = s,
      onError: (_) => fail('no debía fallar'),
    );
    final manejada = await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 3}});
    expect(manejada, isTrue);
    expect(recibido, 3);
    expect(resuelta!.estado, 'atendida');
  });

  test('descartar_sugerencia acepta el id como string (bindings del data model)', () async {
    int? recibido;
    final router = SugerenciaActionRouter(
      atender: (_) async => throw StateError('no debía atender'),
      descartar: (id) async { recibido = id; return _sugerencia(id, 'descartada'); },
      onResuelta: (_) {},
      onError: (_) => fail('no debía fallar'),
    );
    await router.handle({'name': 'descartar_sugerencia', 'context': {'sugerenciaId': '12'}});
    expect(recibido, 12);
  });

  test('un fallo del backend va a onError sin tocar onResuelta', () async {
    Object? error;
    final fallo = Exception('boom');
    final router = SugerenciaActionRouter(
      atender: (_) async => throw fallo,
      descartar: (_) async => throw fallo,
      onResuelta: (_) => fail('no debía resolver'),
      onError: (e) => error = e,
    );
    await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 1}});
    expect(error, fallo);
  });

  test('sin sugerenciaId no hace nada pero sí reclama la acción', () async {
    final router = SugerenciaActionRouter(
      atender: (_) async => fail('no debía llamar'),
      descartar: (_) async => fail('no debía llamar'),
      onResuelta: (_) => fail('no debía resolver'),
      onError: (_) => fail('no debía fallar'),
    );
    expect(await router.handle({'name': 'atender_sugerencia', 'context': {}}), isTrue);
  });
}
