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

/// requestConfirmacion que simula al usuario confirmando de inmediato en
/// el modal HITL — para los tests que no les interesa esa parte.
Future<void> _confirmaDeInmediato(int id, Future<void> Function() onConfirm) => onConfirm();

void main() {
  test('ignora acciones que no son de sugerencias', () async {
    var llamado = false;
    final router = SugerenciaActionRouter(
      atender: (_) async { llamado = true; return _sugerencia(1, 'atendida'); },
      descartar: (_) async { llamado = true; return _sugerencia(1, 'descartada'); },
      requestConfirmacion: (id, onConfirm) async { llamado = true; },
      onResuelta: (_) => llamado = true,
      onError: (_) => llamado = true,
    );
    final manejada = await router.handle({'name': 'confirmar_accion', 'context': {'proposalId': 'p'}});
    expect(manejada, isFalse);
    expect(llamado, isFalse);
  });

  test('atender_sugerencia pide confirmación (HITL) antes de llamar a atender', () async {
    var atenderLlamado = false;
    final router = SugerenciaActionRouter(
      atender: (id) async { atenderLlamado = true; return _sugerencia(id, 'atendida'); },
      descartar: (_) async => throw StateError('no debía descartar'),
      requestConfirmacion: (id, onConfirm) async {
        // Simula que el modal sigue abierto y el usuario NO ha confirmado.
        expect(atenderLlamado, isFalse);
      },
      onResuelta: (_) => fail('no debía resolver sin confirmación'),
      onError: (_) => fail('no debía fallar'),
    );
    await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 3}});
    expect(atenderLlamado, isFalse);
  });

  test('atender_sugerencia SÍ llama a atender cuando el usuario confirma en el modal', () async {
    int? recibido;
    Sugerencia? resuelta;
    final router = SugerenciaActionRouter(
      atender: (id) async { recibido = id; return _sugerencia(id, 'atendida'); },
      descartar: (_) async => throw StateError('no debía descartar'),
      requestConfirmacion: _confirmaDeInmediato,
      onResuelta: (s) => resuelta = s,
      onError: (_) => fail('no debía fallar'),
    );
    final manejada = await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 3}});
    expect(manejada, isTrue);
    expect(recibido, 3);
    expect(resuelta!.estado, 'atendida');
  });

  test('si el usuario cancela el modal, nunca se llama a atender', () async {
    var atenderLlamado = false;
    final router = SugerenciaActionRouter(
      atender: (_) async { atenderLlamado = true; return _sugerencia(1, 'atendida'); },
      descartar: (_) async => throw StateError('no debía descartar'),
      requestConfirmacion: (id, onConfirm) async {
        // No invoca onConfirm -- equivalente a que el usuario tocó "Cancelar".
      },
      onResuelta: (_) => fail('no debía resolver'),
      onError: (_) => fail('no debía fallar'),
    );
    await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 1}});
    expect(atenderLlamado, isFalse);
  });

  test('descartar_sugerencia acepta el id como string (bindings del data model) y no pide confirmación', () async {
    int? recibido;
    final router = SugerenciaActionRouter(
      atender: (_) async => throw StateError('no debía atender'),
      descartar: (id) async { recibido = id; return _sugerencia(id, 'descartada'); },
      requestConfirmacion: (id, onConfirm) async => fail('descartar no debía pedir confirmación'),
      onResuelta: (_) {},
      onError: (_) => fail('no debía fallar'),
    );
    await router.handle({'name': 'descartar_sugerencia', 'context': {'sugerenciaId': '12'}});
    expect(recibido, 12);
  });

  test('un fallo del backend al atender (ya confirmado) va a onError sin tocar onResuelta', () async {
    Object? error;
    final fallo = Exception('boom');
    final router = SugerenciaActionRouter(
      atender: (_) async => throw fallo,
      descartar: (_) async => throw fallo,
      requestConfirmacion: _confirmaDeInmediato,
      onResuelta: (_) => fail('no debía resolver'),
      onError: (e) => error = e,
    );
    await router.handle({'name': 'atender_sugerencia', 'context': {'sugerenciaId': 1}});
    expect(error, fallo);
  });

  test('un fallo del backend al descartar va a onError sin tocar onResuelta', () async {
    Object? error;
    final fallo = Exception('boom');
    final router = SugerenciaActionRouter(
      atender: (_) async => throw fallo,
      descartar: (_) async => throw fallo,
      requestConfirmacion: (id, onConfirm) async => fail('no debía pedir confirmación'),
      onResuelta: (_) => fail('no debía resolver'),
      onError: (e) => error = e,
    );
    await router.handle({'name': 'descartar_sugerencia', 'context': {'sugerenciaId': 1}});
    expect(error, fallo);
  });

  test('sin sugerenciaId no hace nada (ni pide confirmación) pero sí reclama la acción', () async {
    final router = SugerenciaActionRouter(
      atender: (_) async => fail('no debía llamar'),
      descartar: (_) async => fail('no debía llamar'),
      requestConfirmacion: (id, onConfirm) async => fail('no debía pedir confirmación'),
      onResuelta: (_) => fail('no debía resolver'),
      onError: (_) => fail('no debía fallar'),
    );
    expect(await router.handle({'name': 'atender_sugerencia', 'context': {}}), isTrue);
  });
}
