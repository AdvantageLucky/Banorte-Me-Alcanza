// flutter_app/test/yo/validators_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/yo/validators.dart';

void main() {
  group('validarMonto / parsearMonto', () {
    test('acepta formatos con símbolo y comas', () {
      expect(parsearMonto(r'$1,234.50'), 1234.5);
      expect(parsearMonto(' 500 '), 500);
      expect(validarMonto('142.5'), isNull);
    });

    test('rechaza vacío, texto, cero y negativos', () {
      expect(validarMonto(''), 'Escribe un monto válido.');
      expect(validarMonto('abc'), 'Escribe un monto válido.');
      expect(validarMonto('0'), 'El monto debe ser mayor a cero.');
      expect(validarMonto('-5'), 'El monto debe ser mayor a cero.');
    });
  });

  test('validarTexto exige contenido real', () {
    expect(validarTexto('   ', campo: 'El concepto'), 'El concepto no puede quedar vacío.');
    expect(validarTexto('Renta'), isNull);
  });

  test('validarFechaFutura acepta hoy y rechaza ayer', () {
    final hoy = DateTime(2026, 9, 12, 15);
    expect(validarFechaFutura(DateTime(2026, 9, 12), hoy: hoy), isNull);
    expect(validarFechaFutura(DateTime(2026, 9, 11), hoy: hoy), 'La fecha no puede ser anterior a hoy.');
    expect(validarFechaFutura(null, hoy: hoy), 'Elige una fecha.');
  });

  test('validarCuentaDestino solo dígitos de 6 a 18', () {
    expect(validarCuentaDestino('5566778899'), isNull);
    expect(validarCuentaDestino('012 345 678 901 234 567'), isNull);
    expect(validarCuentaDestino('12345'), 'Solo dígitos, entre 6 y 18.');
    expect(validarCuentaDestino('12ab56'), 'Solo dígitos, entre 6 y 18.');
    expect(validarCuentaDestino(''), 'Escribe el número de cuenta.');
  });
}
