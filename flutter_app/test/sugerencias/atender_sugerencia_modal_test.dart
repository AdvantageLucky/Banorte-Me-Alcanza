// flutter_app/test/sugerencias/atender_sugerencia_modal_test.dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/sugerencias/atender_sugerencia_modal.dart';

Future<bool?> _abrir(WidgetTester tester, {required Future<String> Function() onGenerarPropuesta}) async {
  bool? resultado;
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => ElevatedButton(
          onPressed: () async {
            resultado = await showDialog<bool>(
              context: context,
              builder: (_) => AtenderSugerenciaModal(
                titulo: 'Pago próximo: Agua',
                descripcion: '\$450.00 — vence el 15 sep',
                onGenerarPropuesta: onGenerarPropuesta,
              ),
            );
          },
          child: const Text('abrir'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('abrir'));
  await tester.pumpAndSettle();
  return resultado;
}

void main() {
  testWidgets('muestra título y descripción deterministas', (tester) async {
    await _abrir(tester, onGenerarPropuesta: () async => 'x');
    expect(find.text('Pago próximo: Agua'), findsOneWidget);
    expect(find.text('\$450.00 — vence el 15 sep'), findsOneWidget);
    expect(find.text('Ver propuesta del asistente'), findsOneWidget);
  });

  testWidgets('pide la propuesta al asistente solo si el usuario la pide, y la muestra al llegar', (tester) async {
    var llamadas = 0;
    final completer = Completer<String>();
    await _abrir(tester, onGenerarPropuesta: () {
      llamadas++;
      return completer.future;
    });
    expect(llamadas, 0);

    await tester.tap(find.text('Ver propuesta del asistente'));
    await tester.pump();
    expect(find.text('Generando propuesta…'), findsOneWidget);

    completer.complete('Aparta \$107 semanales para cubrir el recibo.');
    await tester.pumpAndSettle();
    expect(llamadas, 1);
    expect(find.text('Aparta \$107 semanales para cubrir el recibo.'), findsOneWidget);
  });

  testWidgets('un error al generar la propuesta se muestra sin tumbar el modal', (tester) async {
    await _abrir(tester, onGenerarPropuesta: () async => throw Exception('boom'));
    await tester.tap(find.text('Ver propuesta del asistente'));
    await tester.pumpAndSettle();
    expect(find.text('No se pudo generar la propuesta, intenta de nuevo.'), findsOneWidget);
  });

  Future<bool?> abrirYActuar(WidgetTester tester, String boton) async {
    bool? resultado;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () async {
              resultado = await showDialog<bool>(
                context: context,
                builder: (_) => AtenderSugerenciaModal(
                  titulo: 't',
                  descripcion: 'd',
                  onGenerarPropuesta: () async => 'x',
                ),
              );
            },
            child: const Text('abrir'),
          ),
        ),
      ),
    ));
    await tester.tap(find.text('abrir'));
    await tester.pumpAndSettle();
    await tester.tap(find.text(boton));
    await tester.pumpAndSettle();
    return resultado;
  }

  testWidgets('"Marcar como atendida" cierra el modal devolviendo true', (tester) async {
    expect(await abrirYActuar(tester, 'Marcar como atendida'), isTrue);
  });

  testWidgets('"Cancelar" cierra el modal devolviendo false', (tester) async {
    expect(await abrirYActuar(tester, 'Cancelar'), isFalse);
  });
}
