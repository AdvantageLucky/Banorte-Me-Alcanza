import { describe, it, expect } from 'vitest';
import { extractTituloDescripcion } from './extractSugerenciaCopy.js';

describe('extractTituloDescripcion', () => {
  it('lee titulo y descripcion de los componentes de la tarjeta', () => {
    const a2uiJson = [
      { version: '0.9', createSurface: { surfaceId: 's1', catalogId: 'x' } },
      {
        version: '0.9',
        updateComponents: {
          surfaceId: 's1',
          components: [
            { id: 'root', component: 'Card', child: 'col' },
            { id: 'titulo', component: 'Text', text: 'Pago próximo: Agua', variant: 'h3' },
            { id: 'descripcion', component: 'Text', text: '$320.00 vence el 15 sep 2026.' },
          ],
        },
      },
    ];

    expect(extractTituloDescripcion(a2uiJson)).toEqual({
      titulo: 'Pago próximo: Agua',
      descripcion: '$320.00 vence el 15 sep 2026.',
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
