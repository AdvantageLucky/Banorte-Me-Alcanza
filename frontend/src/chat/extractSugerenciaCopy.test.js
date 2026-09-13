import { describe, it, expect } from 'vitest';
import { extractTituloDescripcion } from './extractSugerenciaCopy.js';

describe('extractTituloDescripcion', () => {
  it('recombina titulo y descripcion desde el StatCard de la tarjeta', () => {
    const a2uiJson = [
      { version: '0.9', createSurface: { surfaceId: 's1', catalogId: 'x' } },
      {
        version: '0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'root', component: 'Card', child: 'col' },
            { id: 'col', component: 'Column', children: ['titulo', 'stat', 'botones'] },
            { id: 'titulo', component: 'Text', text: 'Pago próximo: Agua', variant: 'h3' },
            {
              id: 'stat',
              component: 'StatCard',
              label: 'Agua',
              value: '$320.00',
              trendLabel: 'vence el 15 sep 2026 y es una parte importante de tu saldo actual',
              tone: 'warning',
            },
          ],
        },
      },
    ];

    expect(extractTituloDescripcion(a2uiJson)).toEqual({
      titulo: 'Pago próximo: Agua',
      descripcion: '$320.00 — vence el 15 sep 2026 y es una parte importante de tu saldo actual',
    });
  });

  it('usa el Text "descripcion" como respaldo si no hay StatCard', () => {
    const a2uiJson = [
      {
        version: '0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'titulo', component: 'Text', text: 'Sugerencia', variant: 'h3' },
            { id: 'descripcion', component: 'Text', text: 'Un texto plano.' },
          ],
        },
      },
    ];

    expect(extractTituloDescripcion(a2uiJson)).toEqual({
      titulo: 'Sugerencia',
      descripcion: 'Un texto plano.',
    });
  });

  it('devuelve cadenas vacías si no hay a2ui_json', () => {
    expect(extractTituloDescripcion(null)).toEqual({ titulo: '', descripcion: '' });
  });

  it('devuelve cadenas vacías si no encuentra los componentes esperados', () => {
    const a2uiJson = [{ version: '0.9', updateComponents: { surfaceId: 's1', components: [] } }];
    expect(extractTituloDescripcion(a2uiJson)).toEqual({ titulo: '', descripcion: '' });
  });
});
