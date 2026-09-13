import { describe, it, expect } from 'vitest';
import { extractSurfaceText } from './extractSurfaceText.js';

// Forma real de los mensajes A2UI que arma el backend (ver
// orchestrator.py/sugerencias_a2ui.py): componentes "planos"
// ({id, component, ...props}, sin envoltura), con props que a veces son un
// literal y a veces un binding {path: "/algo"} resuelto contra el
// dataModel que llega en un mensaje updateDataModel aparte.
describe('extractSurfaceText', () => {
  it('extracts the text of a single literal Text component', () => {
    const messages = [
      { version: 'v0.9', createSurface: { surfaceId: 's1', catalogId: 'x' } },
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [{ id: 'msg', component: 'Text', text: 'Hola, ¿en qué te ayudo?' }],
        },
      },
    ];
    expect(extractSurfaceText(messages)).toBe('Hola, ¿en qué te ayudo?');
  });

  it('resolves a {path} binding against the updateDataModel message', () => {
    const messages = [
      { version: 'v0.9', createSurface: { surfaceId: 's1', catalogId: 'x' } },
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'root', component: 'Card', child: 'msg' },
            { id: 'msg', component: 'Text', text: { path: '/mensaje' } },
          ],
        },
      },
      {
        version: 'v0.9',
        updateDataModel: { surfaceId: 's1', path: '/', value: { mensaje: 'Tu resumen del mes.' } },
      },
    ];
    expect(extractSurfaceText(messages)).toBe('Tu resumen del mes.');
  });

  it('joins the text of multiple components in order', () => {
    const messages = [
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'c1', component: 'Text', text: 'Primera frase.' },
            { id: 'c2', component: 'Text', text: 'Segunda frase.' },
          ],
        },
      },
    ];
    expect(extractSurfaceText(messages)).toBe('Primera frase. Segunda frase.');
  });

  it('reads label/value/trendLabel from a custom component like StatCard', () => {
    const messages = [
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            {
              id: 'c1',
              component: 'StatCard',
              label: 'Gasto del mes',
              value: '$4,200',
              trendLabel: 'subió 12%',
            },
          ],
        },
      },
    ];
    expect(extractSurfaceText(messages)).toBe('Gasto del mes. $4,200. subió 12%');
  });

  it('walks nested arrays of objects like PlanDePago options', () => {
    const messages = [
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            {
              id: 'c1',
              component: 'PlanDePago',
              title: 'Elige tu plan',
              options: [
                { id: 'a', label: 'Plan A', detail: '3 pagos', amount: '$500' },
                { id: 'b', label: 'Plan B', detail: '6 pagos', amount: '$300' },
              ],
            },
          ],
        },
      },
    ];
    expect(extractSurfaceText(messages)).toBe(
      'Elige tu plan. Plan A. 3 pagos. $500. Plan B. 6 pagos. $300',
    );
  });

  it('ignores structural keys that are not readable content (id, component, tone, child, children)', () => {
    const messages = [
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'root', component: 'Card', child: 'col' },
            { id: 'col', component: 'Column', children: ['c1'] },
            { id: 'c1', component: 'StatCard', tone: 'positive', label: 'Ahorro' },
          ],
        },
      },
    ];
    expect(extractSurfaceText(messages)).toBe('Ahorro');
  });

  it('ignores a root updateDataModel whose value is not a plain object, keeping the prior model', () => {
    // Ningún productor real del backend manda esto hoy (siempre value es un
    // objeto, ver orchestrator.py/sugerencias_a2ui.py), pero un valor no
    // objeto en path "/" no debe reemplazar el modelo entero — eso dejaría
    // sin resolver cualquier binding previo (ver extract_surface_text.dart,
    // que ya se comporta así: descarta la actualización en vez de
    // corromper el modelo).
    const messages = [
      { version: 'v0.9', createSurface: { surfaceId: 's1', catalogId: 'x' } },
      {
        version: 'v0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [{ id: 'msg', component: 'Text', text: { path: '/mensaje' } }],
        },
      },
      { version: 'v0.9', updateDataModel: { surfaceId: 's1', path: '/', value: { mensaje: 'Hola' } } },
      { version: 'v0.9', updateDataModel: { surfaceId: 's1', path: '/', value: 'no es un objeto' } },
    ];
    expect(extractSurfaceText(messages)).toBe('Hola');
  });

  it('returns an empty string when there is no updateComponents message', () => {
    expect(extractSurfaceText([{ createSurface: { surfaceId: 's1' } }])).toBe('');
  });

  it('handles an empty or nullish messages array without throwing', () => {
    expect(extractSurfaceText([])).toBe('');
    expect(extractSurfaceText(null)).toBe('');
    expect(extractSurfaceText(undefined)).toBe('');
  });
});
