import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import { ApiError } from '../api/client.js';

export default function LoginView() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);

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

  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      // Si no se está enviando ya, ejecutamos la función pasando el evento
      if (!submitting) {
        handleSubmit(event);
      }
    }
  };

  return (
    <div className="login-view">
      <header className="login-navbar">
        <span className="login-navbar-brand">Banorte</span>
        <span className="login-navbar-tagline"> — ¿Me alcanza?</span>
      </header>

      <div className="login-stage">
        <div className="login-panel">
          <div className="login-card">
            <form className="login-form" onSubmit={handleSubmit}>
              <p className="login-card-subtitle">Inicia sesión para continuar.</p>
              <label>
                Usuario
                <input value={username} onKeyDown={handleKeyDown} onChange={(event) => setUsername(event.target.value)} required />
              </label>
              <label>
                Contraseña
                <input
                  type="password"
                  value={password}
                  onKeyDown={handleKeyDown}
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
        </div>

        <div className="login-video-wrap">
          <div className="login-animation">
            <video
              className="login-video"
              autoPlay
              loop
              muted
              playsInline
              onError={() => setVideoFailed(true)}
            >
              <source src="/videos/animacion2.webm" type="video/webm" />
            </video>
          </div>

          <div className="login-video-text">
            <h2>¡Hola!</h2>
            <p>Bienvenido a nuestra plataforma.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
