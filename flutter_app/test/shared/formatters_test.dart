// flutter_app/test/shared/formatters_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/shared/formatters.dart';

void main() {
  group('formatMonto', () {
    test('separa miles con coma y siempre muestra dos decimales', () {
      expect(formatMonto(1234.5), r'$1,234.50');
      expect(formatMonto(500), r'$500.00');
      expect(formatMonto(12500), r'$12,500.00');
      expect(formatMonto(1000000), r'$1,000,000.00');
    });

    test('pone el signo antes del símbolo en negativos', () {
      expect(formatMonto(-570), r'-$570.00');
    });

    test('redondea centavos sin desbordar el entero', () {
      expect(formatMonto(0.999), r'$1.00');
      expect(formatMonto(142.5), r'$142.50');
    });

    test('formatMontoCorto quita los centavos', () {
      expect(formatMontoCorto(2400), r'$2,400');
      expect(formatMontoCorto(319.6), r'$320');
    });
  });

  group('fechas', () {
    test('formatFecha abrevia el mes en español', () {
      expect(formatFecha('2026-09-15'), '15 sep');
      expect(formatFecha('2026-01-03'), '3 ene');
      expect(formatFechaLarga('2026-12-25'), '25 dic 2026');
    });

    test('toFechaIso produce el formato del backend con ceros', () {
      expect(toFechaIso(DateTime(2026, 3, 7)), '2026-03-07');
    });

    test('diasHasta cuenta días completos ignorando la hora', () {
      final hoy = DateTime(2026, 9, 12, 23, 59);
      expect(diasHasta('2026-09-13', hoy: hoy), 1);
      expect(diasHasta('2026-09-12', hoy: hoy), 0);
      expect(diasHasta('2026-09-10', hoy: hoy), -2);
    });

    test('describirDias habla como una persona', () {
      expect(describirDias(0), 'hoy');
      expect(describirDias(1), 'mañana');
      expect(describirDias(4), 'en 4 días');
      expect(describirDias(-1), 'ayer');
      expect(describirDias(-3), 'hace 3 días');
    });
  });

  test('describirFrecuencia traduce y deja pasar valores desconocidos', () {
    expect(describirFrecuencia('quincenal'), 'cada quincena');
    expect(describirFrecuencia('bimestral'), 'bimestral');
  });
}
