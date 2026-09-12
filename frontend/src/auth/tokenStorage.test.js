import { describe, it, expect, beforeEach } from 'vitest';
import { readStoredToken, writeStoredToken, clearStoredToken } from './tokenStorage.js';

function createFakeStorage() {
  const store = new Map();
  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key),
  };
}

describe('tokenStorage', () => {
  beforeEach(() => {
    globalThis.localStorage = createFakeStorage();
  });

  it('returns null when nothing is stored', () => {
    expect(readStoredToken()).toBeNull();
  });

  it('round-trips a token through write/read', () => {
    writeStoredToken('jwt-abc');
    expect(readStoredToken()).toBe('jwt-abc');
  });

  it('clears a stored token', () => {
    writeStoredToken('jwt-abc');
    clearStoredToken();
    expect(readStoredToken()).toBeNull();
  });

  it('does not throw when localStorage is unavailable', () => {
    globalThis.localStorage = undefined;
    expect(() => writeStoredToken('jwt-abc')).not.toThrow();
    expect(readStoredToken()).toBeNull();
    expect(() => clearStoredToken()).not.toThrow();
  });
});
