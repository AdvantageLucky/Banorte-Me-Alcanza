// flutter_app/test/yo/quincena_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/models/models.dart';
import 'package:me_alcanza/yo/quincena.dart';

Recurrente _r(int id, String etiqueta, double monto, String fecha) =>
    Recurrente(id: id, etiqueta: etiqueta, monto: monto, frecuencia: 'mensual', proximaFecha: fecha);

void main() {
  final hoy = DateTime(2026, 9, 12);

  test('con el seed de ana: nómina mañana y ningún pago cae antes', () {
    final riel = construirRiel(
      hoy: hoy,
      ingresos: [_r(1, 'Nómina', 12500, '2026-09-13')],
      gastosFijos: [
        _r(1, 'Agua', 320, '2026-09-15'),
        _r(2, 'Luz', 450, '2026-09-15'),
        _r(3, 'Colegiatura hijo 1', 2400, '2026-09-16'),
      ],
    );
    expect(riel.tieneNomina, isTrue);
    expect(riel.diasTotales, 1);
    expect(riel.nomina!.dia, 1);
    expect(riel.pagos, isEmpty, reason: 'los pagos son después de la nómina');
    expect(riel.totalPagos, 0);
    expect(describirNomina(riel), r'Mañana cobras $12,500');
  });

  test('pagos entre hoy y la nómina quedan ordenados y sumados', () {
    final riel = construirRiel(
      hoy: hoy,
      ingresos: [_r(1, 'Nómina', 12500, '2026-09-20')],
      gastosFijos: [
        _r(3, 'Colegiatura', 2400, '2026-09-16'),
        _r(1, 'Agua', 320, '2026-09-15'),
        _r(9, 'Seguro', 999, '2026-10-01'),
      ],
    );
    expect(riel.diasTotales, 8);
    expect(riel.pagos.map((e) => e.etiqueta), ['Agua', 'Colegiatura']);
    expect(riel.totalPagos, 2720);
    expect(riel.saldoProyectado(500), -2220);
    expect(riel.posicion(riel.pagos.first), closeTo(3 / 8, 1e-9));
    expect(riel.posicion(riel.nomina!), 1.0);
    expect(describirNomina(riel), '8 días para tu nómina');
  });

  test('sin ingresos el riel mide 14 días y lo dice', () {
    final riel = construirRiel(
      hoy: hoy,
      ingresos: const [],
      gastosFijos: [_r(1, 'Renta', 4000, '2026-09-25'), _r(2, 'Lejano', 1, '2026-12-01')],
    );
    expect(riel.tieneNomina, isFalse);
    expect(riel.diasTotales, 14);
    expect(riel.pagos.single.etiqueta, 'Renta');
    expect(describirNomina(riel), 'Sin ingreso programado');
  });

  test('un ingreso ya vencido no cuenta como próxima nómina', () {
    final riel = construirRiel(
      hoy: hoy,
      ingresos: [_r(1, 'Vieja', 100, '2026-09-01'), _r(2, 'Bono', 300, '2026-09-30')],
      gastosFijos: const [],
    );
    expect(riel.nomina!.etiqueta, 'Bono');
    expect(riel.diasTotales, 18);
  });

  test('nómina hoy: el riel no colapsa a cero', () {
    final riel = construirRiel(
      hoy: hoy,
      ingresos: [_r(1, 'Nómina', 12500, '2026-09-12')],
      gastosFijos: [_r(1, 'Agua', 320, '2026-09-12')],
    );
    expect(riel.diasTotales, 1);
    expect(riel.posicion(riel.pagos.single), 0.0);
    expect(describirNomina(riel), r'Hoy cobras $12,500');
  });
}
