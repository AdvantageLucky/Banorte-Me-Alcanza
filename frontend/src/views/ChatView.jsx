import { useEffect, useMemo, useState, Fragment } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface, basicCatalog } from '@a2ui/react/v0_9';
import { injectStyles, removeStyles } from '@a2ui/react/styles';
import { apiClient } from '../api/client.js';
import { createActionHandler } from '../chat/actionHandler.js';
import { dropDuplicateCreateSurface } from '../chat/messageFilter.js';
import { extractSurfaceId } from '../chat/extractSurfaceId.js';
import Typewriter from '../components/typewritter.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import logo from '../assets/images/logo.svg';

export default function ChatView() {
  const { token, logout } = useAuth();
  const [mensaje, setMensaje] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  // Transcripción de la conversación: cada turno queda como su propia entrada
  // (nunca se sobrescribe uno anterior), en el orden real en que ocurrieron —
  // el backend le da a cada turno del agente su propio surfaceId único.
  const [turns, setTurns] = useState([]);

  function handleApiError(err, fallback) {
    if (err?.status === 401) {
      logout();
      return;
    }
    setErrorMessage(err?.detail || fallback);
  }

  function appendAgentTurn(messages) {
    const surfaceId = extractSurfaceId(messages);
    if (surfaceId) {
      setTurns((prev) => [...prev, { kind: 'agent', id: surfaceId, surfaceId }]);
    }
  }

  const processor = useMemo(() => {
    let proc;
    const handleAction = createActionHandler({
      confirmAction: (proposalId) => apiClient.confirmAction(token, proposalId),
      onMessages: (messages) => {
        setErrorMessage(null);
        proc.processMessages(
          dropDuplicateCreateSurface(messages, new Set(proc.model.surfacesMap.keys())),
        );
        appendAgentTurn(messages);
      },
      onError: (err) => handleApiError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
    });
    proc = new MessageProcessor([basicCatalog], handleAction);
    return proc;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    injectStyles();
    return () => removeStyles();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const texto = mensaje.trim();
    if (!texto || sending) {
      return;
    }
    setSending(true);
    setErrorMessage(null);
    setTurns((prev) => [...prev, { kind: 'user', id: crypto.randomUUID(), text: texto }]);
    setMensaje('');
    try {
      const { a2ui_messages } = await apiClient.sendMessage(token, texto);
      processor.processMessages(
        dropDuplicateCreateSurface(a2ui_messages, new Set(processor.model.surfacesMap.keys())),
      );
      appendAgentTurn(a2ui_messages);
    } catch (err) {
      handleApiError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-view">
      <header className="chat-header">
        <span>
          <span>Banorte</span>
          <span className="chat-header-subtitle"> — ¿Me Alcanza?</span>
        </span>
        <button type="button" onClick={logout}>
          Salir
        </button>
      </header>
      <main className="chat-surfaces">
        {turns.length === 0 && (
          <Typewriter />
        )}
        {turns.map((turn) => {
          if (turn.kind === 'user') {
            return (
              <p key={turn.id} className="chat-message-user">
                {turn.text}
              </p>
            );
          }
          const surface = processor.model.getSurface(turn.surfaceId);
          if (!surface) {
            return null;
          }
          return (
            <div className="chat-bot" key={turn.id}>
              <img className="chat-logo" src={logo} alt="Logo" width="40" height="40" />
              <A2uiSurface key={turn.id} surface={surface} />
            </div>
          );
        })}
      </main>
      {errorMessage && <p className="chat-error">{errorMessage}</p>}
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={mensaje}
          onChange={(event) => setMensaje(event.target.value)}
          placeholder="Escribe tu mensaje..."
          disabled={sending}
        />
        <button type="submit" disabled={sending}>
          {sending ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </div>
  );
}
