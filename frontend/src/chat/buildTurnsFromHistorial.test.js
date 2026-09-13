import { describe, it, expect, vi } from 'vitest';
import { buildTurnsFromHistorial } from './buildTurnsFromHistorial.js';

describe('buildTurnsFromHistorial', () => {
  it('convierte un turno de usuario en un turno de texto', () => {
    const processMessages = vi.fn();
    const extractSurfaceId = vi.fn();

    const turns = buildTurnsFromHistorial(
      [{ rol: 'user', contenido: 'hola', a2ui_json: null }],
      { processMessages, extractSurfaceId },
    );

    expect(turns).toEqual([expect.objectContaining({ kind: 'user', text: 'hola' })]);
    expect(processMessages).not.toHaveBeenCalled();
  });

  it('procesa el a2ui_json de un turno del modelo y lo deja como turno de agente', () => {
    const a2uiJson = [{ createSurface: { surfaceId: 'surf-1' } }];
    const processMessages = vi.fn();
    const extractSurfaceId = vi.fn().mockReturnValue('surf-1');

    const turns = buildTurnsFromHistorial(
      [{ rol: 'model', contenido: 'texto crudo', a2ui_json: a2uiJson }],
      { processMessages, extractSurfaceId },
    );

    expect(processMessages).toHaveBeenCalledWith(a2uiJson);
    expect(turns).toEqual([{ kind: 'agent', id: 'surf-1', surfaceId: 'surf-1', messages: a2uiJson }]);
  });

  it('cae a texto plano cuando el turno del modelo no tiene a2ui_json', () => {
    const processMessages = vi.fn();
    const extractSurfaceId = vi.fn();

    const turns = buildTurnsFromHistorial(
      [{ rol: 'model', contenido: 'esto no parseó', a2ui_json: null }],
      { processMessages, extractSurfaceId },
    );

    expect(processMessages).not.toHaveBeenCalled();
    expect(turns).toEqual([expect.objectContaining({ kind: 'agent-text', text: 'esto no parseó' })]);
  });

  it('preserva el orden y procesa varios turnos en secuencia', () => {
    const processMessages = vi.fn();
    const extractSurfaceId = vi.fn().mockReturnValueOnce('surf-1').mockReturnValueOnce('surf-2');

    const turns = buildTurnsFromHistorial(
      [
        { rol: 'user', contenido: 'primero', a2ui_json: null },
        { rol: 'model', contenido: 'x', a2ui_json: [{ createSurface: { surfaceId: 'surf-1' } }] },
        { rol: 'user', contenido: 'segundo', a2ui_json: null },
        { rol: 'model', contenido: 'y', a2ui_json: [{ createSurface: { surfaceId: 'surf-2' } }] },
      ],
      { processMessages, extractSurfaceId },
    );

    expect(turns.map((t) => t.kind)).toEqual(['user', 'agent', 'user', 'agent']);
    expect(processMessages).toHaveBeenCalledTimes(2);
  });
});
