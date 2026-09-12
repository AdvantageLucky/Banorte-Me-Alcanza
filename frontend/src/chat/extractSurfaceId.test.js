import { describe, it, expect } from 'vitest';
import { extractSurfaceId } from './extractSurfaceId.js';

describe('extractSurfaceId', () => {
  it('returns the surfaceId from the createSurface message', () => {
    const messages = [
      { createSurface: { surfaceId: 'turno-abc123', catalogId: 'x' } },
      { updateComponents: { surfaceId: 'turno-abc123', components: [] } },
    ];
    expect(extractSurfaceId(messages)).toBe('turno-abc123');
  });

  it('returns null when there is no createSurface message', () => {
    const messages = [{ updateComponents: { surfaceId: 'turno-abc123', components: [] } }];
    expect(extractSurfaceId(messages)).toBeNull();
  });

  it('handles an empty or nullish messages array without throwing', () => {
    expect(extractSurfaceId([])).toBeNull();
    expect(extractSurfaceId(null)).toBeNull();
    expect(extractSurfaceId(undefined)).toBeNull();
  });
});
