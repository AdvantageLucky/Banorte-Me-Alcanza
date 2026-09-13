// flutter_app/test/a2ui/me_alcanza_catalog_test.dart
//
// Renderiza una superficie real de genui con el catalogId propio del
// backend y los tres componentes de dominio. Si el backend cambia el id o
// las props sin actualizar Flutter, esto falla antes que la demo.
import 'package:a2ui_core/a2ui_core.dart' as core;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:genui/genui.dart';
import 'package:me_alcanza/a2ui/me_alcanza_catalog.dart';

const _surface = 'prueba';

List<Map<String, dynamic>> _mensajes(List<Map<String, dynamic>> componentes, {Map<String, dynamic>? data}) => [
      {'version': 'v0.9', 'createSurface': {'surfaceId': _surface, 'catalogId': meAlcanzaCatalogId}},
      {'version': 'v0.9', 'updateComponents': {'surfaceId': _surface, 'components': componentes}},
      if (data != null)
        {'version': 'v0.9', 'updateDataModel': {'surfaceId': _surface, 'path': '/', 'value': data}},
    ];

Future<SurfaceController> _montar(WidgetTester tester, List<Map<String, dynamic>> mensajes) async {
  final controller = SurfaceController(catalogs: [BasicCatalogItems.asCatalog(), buildMeAlcanzaCatalog()]);
  for (final m in mensajes) {
    controller.handleMessage(core.A2uiMessage.fromJson(m));
  }
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: Surface(surfaceContext: controller.contextFor(_surface))),
  ));
  await tester.pump();
  return controller;
}

void main() {
  testWidgets('StatCard dentro de una Card del catálogo básico', (tester) async {
    final controller = await _montar(tester, _mensajes([
      {'id': 'root', 'component': 'Card', 'child': 'stat'},
      {
        'id': 'stat',
        'component': 'StatCard',
        'label': 'Salud financiera',
        'value': '82/100',
        'trend': 'up',
        'trendLabel': 'Mejoró',
        'tone': 'positive',
      },
    ]));
    expect(tester.takeException(), isNull);
    expect(find.text('Salud financiera'), findsOneWidget);
    expect(find.text('82/100'), findsOneWidget);
    expect(find.text('Mejoró'), findsOneWidget);
    expect(find.byType(FallbackWidget), findsNothing);
    controller.dispose();
  });

  testWidgets('BarChart pinta una barra por dato con el prefijo de moneda', (tester) async {
    final controller = await _montar(tester, _mensajes([
      {
        'id': 'root',
        'component': 'BarChart',
        'title': 'Gasto por categoría',
        'valuePrefix': r'$',
        'bars': [
          {'label': 'Transferencias', 'value': 500, 'tone': 'negative'},
          {'label': 'Apartados', 'value': 142.5},
        ],
      },
    ]));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Gasto por categoría'), findsOneWidget);
    expect(find.text('Transferencias'), findsOneWidget);
    expect(find.text(r'$500.00'), findsOneWidget);
    expect(find.text(r'$142.50'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNWidgets(2));
    controller.dispose();
  });

  testWidgets('PlanDePago escribe la opción elegida en el data model', (tester) async {
    final controller = await _montar(
      tester,
      _mensajes([
        {
          'id': 'root',
          'component': 'PlanDePago',
          'title': 'Elige tu plan',
          'options': [
            {'id': '12m', 'label': '12 meses', 'detail': 'CAT 32.4%', 'amount': r'$1,690.00', 'highlighted': true},
            {'id': '18m', 'label': '18 meses', 'detail': 'CAT 34.1%', 'amount': r'$1,215.00'},
          ],
          'selectedId': {'path': '/planSeleccionado'},
        },
      ], data: {'planSeleccionado': '12m'}),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Elige tu plan'), findsOneWidget);
    expect(find.text('Recomendado'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle), findsOneWidget);

    await tester.tap(find.text('18 meses'));
    await tester.pumpAndSettle();

    expect(controller.contextFor(_surface).dataModel.getValue<String>(DataPath('/planSeleccionado')), '18m');
    controller.dispose();
  });

  testWidgets('LineChart pinta la serie sin excepción y marca el punto crítico', (tester) async {
    final controller = await _montar(tester, _mensajes([
      {
        'id': 'root',
        'component': 'LineChart',
        'title': 'Proyección de saldo',
        'valuePrefix': r'$',
        'points': [
          {'label': '11 sep', 'value': 500},
          {'label': '15 sep', 'value': -570, 'tone': 'negative'},
        ],
        'thresholdValue': 0,
        'thresholdLabel': 'Saldo en \$0',
      },
    ]));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Proyección de saldo'), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
    expect(find.byType(FallbackWidget), findsNothing);
    controller.dispose();
  });

  testWidgets('LineChart con un solo punto no truena (se oculta)', (tester) async {
    final controller = await _montar(tester, _mensajes([
      {
        'id': 'root',
        'component': 'LineChart',
        'points': [
          {'label': '11 sep', 'value': 500},
        ],
      },
    ]));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    controller.dispose();
  });

  testWidgets('ApartadoPlanner recalcula periodos EN EL CLIENTE al mover el slider', (tester) async {
    final controller = await _montar(
      tester,
      _mensajes([
        {
          'id': 'root',
          'component': 'ApartadoPlanner',
          'title': 'Ajusta tu apartado',
          'montoObjetivo': 570,
          'periodicidadLabel': 'semanal',
          'minMonto': 50,
          'maxMonto': 300,
          'montoPorPeriodo': {'path': '/montoPorPeriodo'},
        },
      ], data: {'montoPorPeriodo': 150.0}),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    // 570 / 150 = 3.8 -> 4 pagos.
    expect(find.text('4'), findsOneWidget);

    await tester.drag(find.byType(Slider), const Offset(500, 0));
    await tester.pumpAndSettle();

    final nuevoMonto =
        controller.contextFor(_surface).dataModel.getValue<double>(DataPath('/montoPorPeriodo'));
    expect(nuevoMonto, isNotNull);
    expect(nuevoMonto, greaterThan(150.0));
    controller.dispose();
  });

  testWidgets('DonutChart pinta las porciones y resalta al tocar la leyenda', (tester) async {
    final controller = await _montar(
      tester,
      _mensajes([
        {
          'id': 'root',
          'component': 'DonutChart',
          'title': 'Gasto por categoría',
          'centerLabel': 'Total',
          'centerValue': r'$5,099.00',
          'slices': [
            {'id': 'renta', 'label': 'Renta', 'value': 4500},
            {'id': 'internet', 'label': 'Internet', 'value': 599},
          ],
          'selectedId': {'path': '/categoriaResaltada'},
        },
      ]),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Gasto por categoría'), findsOneWidget);
    expect(find.text('Renta'), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
    expect(find.byType(FallbackWidget), findsNothing);

    await tester.tap(find.text('Internet'));
    await tester.pumpAndSettle();

    expect(
      controller.contextFor(_surface).dataModel.getValue<String>(DataPath('/categoriaResaltada')),
      'internet',
    );
    controller.dispose();
  });

  testWidgets('DonutChart con una sola porción no truena (se oculta)', (tester) async {
    final controller = await _montar(tester, _mensajes([
      {
        'id': 'root',
        'component': 'DonutChart',
        'slices': [
          {'id': 'renta', 'label': 'Renta', 'value': 4500},
        ],
      },
    ]));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    controller.dispose();
  });

  testWidgets('BudgetAllocator recalcula lo sin asignar EN EL CLIENTE al mover el slider', (tester) async {
    final controller = await _montar(
      tester,
      _mensajes([
        {
          'id': 'root',
          'component': 'BudgetAllocator',
          'title': 'Reparte tu margen',
          'total': 1200,
          'categorias': [
            {'id': 'laptop', 'label': 'Laptop nueva'},
            {'id': 'libre', 'label': 'Sin asignar'},
          ],
          'categoriaSeleccionada': {'path': '/categoriaSeleccionada'},
          'montoAsignado': {'path': '/montoAsignado'},
        },
      ], data: {'categoriaSeleccionada': 'laptop', 'montoAsignado': 500.0}),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Sin asignar: \$700.00 de \$1,200.00'), findsOneWidget);

    await tester.tap(find.text('Sin asignar'));
    await tester.pumpAndSettle();
    expect(
      controller.contextFor(_surface).dataModel.getValue<String>(DataPath('/categoriaSeleccionada')),
      'libre',
    );

    await tester.drag(find.byType(Slider), const Offset(200, 0));
    await tester.pumpAndSettle();
    final nuevoMonto =
        controller.contextFor(_surface).dataModel.getValue<double>(DataPath('/montoAsignado'));
    expect(nuevoMonto, isNotNull);
    expect(nuevoMonto, greaterThan(500.0));
    controller.dispose();
  });

  testWidgets('una superficie con el id básico sigue renderizando (modo offline)', (tester) async {
    final controller = await _montar(tester, [
      {
        'version': 'v0.9',
        'createSurface': {
          'surfaceId': _surface,
          'catalogId': 'https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json',
        },
      },
      {
        'version': 'v0.9',
        'updateComponents': {
          'surfaceId': _surface,
          'components': [
            {'id': 'root', 'component': 'Text', 'text': 'Modo offline'},
          ],
        },
      },
    ]);
    expect(tester.takeException(), isNull);
    expect(find.text('Modo offline'), findsOneWidget);
    controller.dispose();
  });
}
