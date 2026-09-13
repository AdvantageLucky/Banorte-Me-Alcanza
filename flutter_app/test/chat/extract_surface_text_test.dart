// flutter_app/test/chat/extract_surface_text_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:me_alcanza/chat/extract_surface_text.dart';

// Forma real de los mensajes A2UI que arma el backend (ver
// orchestrator.py/sugerencias_a2ui.py): componentes "planos"
// ({id, component, ...props}, sin envoltura), con props que a veces son un
// literal y a veces un binding {path: "/algo"} resuelto contra el
// dataModel que llega en un mensaje updateDataModel aparte. Mismo
// comportamiento que frontend/src/chat/extractSurfaceText.js — se mantienen
// en sync a mano.
void main() {
  group('extractSurfaceText', () {
    test('extracts the text of a single literal Text component', () {
      final messages = [
        {
          'version': 'v0.9',
          'createSurface': {'surfaceId': 's1', 'catalogId': 'x'},
        },
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {'id': 'msg', 'component': 'Text', 'text': 'Hola, ¿en qué te ayudo?'},
            ],
          },
        },
      ];
      expect(extractSurfaceText(messages), 'Hola, ¿en qué te ayudo?');
    });

    test('resolves a {path} binding against the updateDataModel message', () {
      final messages = [
        {
          'version': 'v0.9',
          'createSurface': {'surfaceId': 's1', 'catalogId': 'x'},
        },
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {'id': 'root', 'component': 'Card', 'child': 'msg'},
              {
                'id': 'msg',
                'component': 'Text',
                'text': {'path': '/mensaje'},
              },
            ],
          },
        },
        {
          'version': 'v0.9',
          'updateDataModel': {
            'surfaceId': 's1',
            'path': '/',
            'value': {'mensaje': 'Tu resumen del mes.'},
          },
        },
      ];
      expect(extractSurfaceText(messages), 'Tu resumen del mes.');
    });

    test('joins the text of multiple components in order', () {
      final messages = [
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {'id': 'c1', 'component': 'Text', 'text': 'Primera frase.'},
              {'id': 'c2', 'component': 'Text', 'text': 'Segunda frase.'},
            ],
          },
        },
      ];
      expect(extractSurfaceText(messages), 'Primera frase. Segunda frase.');
    });

    test('reads label/value/trendLabel from a custom component like StatCard', () {
      final messages = [
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {
                'id': 'c1',
                'component': 'StatCard',
                'label': 'Gasto del mes',
                'value': '\$4,200',
                'trendLabel': 'subió 12%',
              },
            ],
          },
        },
      ];
      expect(extractSurfaceText(messages), 'Gasto del mes. \$4,200. subió 12%');
    });

    test('walks nested arrays of objects like PlanDePago options', () {
      final messages = [
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {
                'id': 'c1',
                'component': 'PlanDePago',
                'title': 'Elige tu plan',
                'options': [
                  {'id': 'a', 'label': 'Plan A', 'detail': '3 pagos', 'amount': '\$500'},
                  {'id': 'b', 'label': 'Plan B', 'detail': '6 pagos', 'amount': '\$300'},
                ],
              },
            ],
          },
        },
      ];
      expect(
        extractSurfaceText(messages),
        'Elige tu plan. Plan A. 3 pagos. \$500. Plan B. 6 pagos. \$300',
      );
    });

    test('ignores structural keys that are not readable content (id, component, tone, child, children)', () {
      final messages = [
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': 's1',
            'components': [
              {'id': 'root', 'component': 'Card', 'child': 'col'},
              {
                'id': 'col',
                'component': 'Column',
                'children': ['c1'],
              },
              {'id': 'c1', 'component': 'StatCard', 'tone': 'positive', 'label': 'Ahorro'},
            ],
          },
        },
      ];
      expect(extractSurfaceText(messages), 'Ahorro');
    });

    test(
      'ignores a root updateDataModel whose value is not a plain object, keeping the prior model',
      () {
        // Ningún productor real del backend manda esto hoy (siempre value
        // es un objeto, ver orchestrator.py/sugerencias_a2ui.py), pero un
        // valor no-Map en path "/" no debe reemplazar el modelo entero —
        // eso dejaría sin resolver cualquier binding previo. Mismo
        // comportamiento fijado del lado de extractSurfaceText.js.
        final messages = [
          {
            'version': 'v0.9',
            'createSurface': {'surfaceId': 's1', 'catalogId': 'x'},
          },
          {
            'version': 'v0.9',
            'updateComponents': {
              'surfaceId': 's1',
              'components': [
                {
                  'id': 'msg',
                  'component': 'Text',
                  'text': {'path': '/mensaje'},
                },
              ],
            },
          },
          {
            'version': 'v0.9',
            'updateDataModel': {
              'surfaceId': 's1',
              'path': '/',
              'value': {'mensaje': 'Hola'},
            },
          },
          {
            'version': 'v0.9',
            'updateDataModel': {'surfaceId': 's1', 'path': '/', 'value': 'no es un objeto'},
          },
        ];
        expect(extractSurfaceText(messages), 'Hola');
      },
    );

    test('returns an empty string when there is no updateComponents message', () {
      expect(
        extractSurfaceText([
          {
            'createSurface': {'surfaceId': 's1'},
          },
        ]),
        '',
      );
    });

    test('handles an empty or nullish messages list without throwing', () {
      expect(extractSurfaceText([]), '');
      expect(extractSurfaceText(null), '');
    });
  });
}
