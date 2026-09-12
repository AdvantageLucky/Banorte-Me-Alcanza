import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { ApiError } from '../api/client.js';

export default function LoginView() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || 'Usuario o contraseña incorrectos.');
      } else {
        setError('No se pudo contactar el servidor. Verifica que el backend esté corriendo.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-view">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>me-alcanza</h1>
        <label>
          Usuario
          <input value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error && <p className="login-error">{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
