import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { apiClient } from '../api/client.js';
import { readStoredToken, writeStoredToken, clearStoredToken } from './tokenStorage.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => readStoredToken());

  const login = useCallback(async (username, password) => {
    const { token: newToken } = await apiClient.login(username, password);
    writeStoredToken(newToken);
    setToken(newToken);
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
  }, []);

  const value = useMemo(() => ({ token, login, logout }), [token, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de un AuthProvider');
  }
  return context;
}
