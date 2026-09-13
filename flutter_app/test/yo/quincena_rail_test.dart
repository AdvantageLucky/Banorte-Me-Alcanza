// flutter_app/test/yo/quincena_rail_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/models/models.dart';
import 'package:me_alcanza/yo/quincena.dart';
import 'package:me_alcanza/yo/quincena_rail.dart';

Recurrente _r(int id, String etiqueta, double monto, DateTime fecha) => Recurrente(
      id: id,
      etiqueta: etiqueta,
      monto: monto,
      frecuencia: 'mensual',
      proximaFecha: '${fecha.year}-${fecha.month.toString().padLeft(2, '0')}-${fecha.day.toString().padLeft(2, '0')}',
    );

void main() {
  testWidgets('pinta el riel con nómina y pagos sin lanzar, y describe el contenido', (tester) async {
    final hoy = DateTime.now();
    final riel = construirRiel(
      ingresos: [_r(1, 'Nómina', 12500, hoy.add(const Duration(days: 10)))],
      gastosFijos: [
        _r(1, 'Agua', 320, hoy.add(const Duration(days: 3))),
        _r(2, 'Luz', 450, hoy.add(const Duration(days: 3))),
        _r(3, 'Colegiatura', 2400, hoy.add(const Duration(days: 4))),
      ],
    );

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: SizedBox(width: 360, child: QuincenaRail(riel: riel))),
    ));

    expect(tester.takeException(), isNull);
    expect(find.byType(CustomPaint), findsWidgets);
    final semantics = tester.getSemantics(find.byType(QuincenaRail));
    expect(semantics.label, contains('Nómina'));
    expect(semantics.label, contains('Colegiatura'));
  });

  testWidgets('sin nómina ni pagos también pinta y lo dice', (tester) async {
    final riel = construirRiel(ingresos: const [], gastosFijos: const []);
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: SizedBox(width: 360, child: QuincenaRail(riel: riel))),
    ));
    expect(tester.takeException(), isNull);
    expect(tester.getSemantics(find.byType(QuincenaRail)).label, 'Sin pagos ni ingresos próximos');
  });
}
