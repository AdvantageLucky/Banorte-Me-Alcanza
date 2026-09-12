import { describe, it, expect } from 'vitest';
import { dropDuplicateCreateSurface } from './messageFilter.js';

describe('dropDuplicateCreateSurface', () => {
  it('passes through messages when the surface does not exist yet', () => {
    const messages = [
      { createSurface: { surfaceId: 'main', catalogId: 'x' } },
      { updateComponents: { surfaceId: 'main', components: [] } },
    ];
    const result = dropDuplicateCreateSurface(messages, new Set());
    expect(result).toEqual(messages);
  });

  it('drops a createSurface message for a surface that already exists, keeps the rest', () => {
    const messages = [
      { createSurface: { surfaceId: 'main', catalogId: 'x' } },
      { updateComponents: { surfaceId: 'main', components: [{ id: 'root' }] } },
      { updateDataModel: { surfaceId: 'main', path: '/', value: { msg: 'hola' } } },
    ];
    const result = dropDuplicateCreateSurface(messages, new Set(['main']));
    expect(result).toEqual([
      { updateComponents: { surfaceId: 'main', components: [{ id: 'root' }] } },
      { updateDataModel: { surfaceId: 'main', path: '/', value: { msg: 'hola' } } },
    ]);
  });

  it('only drops createSurface for surfaces that already exist, keeps others', () => {
    const messages = [
      { createSurface: { surfaceId: 'main', catalogId: 'x' } },
      { createSurface: { surfaceId: 'confirmacion', catalogId: 'x' } },
    ];
    const result = dropDuplicateCreateSurface(messages, new Set(['main']));
    expect(result).toEqual([{ createSurface: { surfaceId: 'confirmacion', catalogId: 'x' } }]);
  });

  it('handles an empty or nullish messages array without throwing', () => {
    expect(dropDuplicateCreateSurface(null, new Set())).toEqual([]);
    expect(dropDuplicateCreateSurface(undefined, new Set())).toEqual([]);
    expect(dropDuplicateCreateSurface([], new Set())).toEqual([]);
  });
});
