import { useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface, basicCatalog } from '@a2ui/react/v0_9';
import { injectStyles, removeStyles } from '@a2ui/react/styles';
import { apiClient } from '../api/client.js';
import { createActionHandler } from '../chat/actionHandler.js';
import { useAuth } from '../auth/AuthContext.jsx';

export default function ChatView() {
  const { token, logout } = useAuth();
  const [mensaje, setMensaje] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [surfaces, setSurfaces] = useState([]);

  function handleApiError(err, fallback) {
    if (err?.status === 401) {
      logout();
      return;
    }
    setErrorMessage(err?.detail || fallback);
  }

  const processor = useMemo(() => {
    let proc;
    const handleAction = createActionHandler({
      confirmAction: (proposalId) => apiClient.confirmAction(token, proposalId),
      onMessages: (messages) => proc.processMessages(messages),
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

  useEffect(() => {
    const sync = () => setSurfaces(Array.from(processor.model.surfacesMap.values()));
    sync();
    const createdSub = processor.onSurfaceCreated(sync);
    const deletedSub = processor.onSurfaceDeleted(sync);
    return () => {
      createdSub.unsubscribe();
      deletedSub.unsubscribe();
    };
  }, [processor]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!mensaje.trim() || sending) {
      return;
    }
    setSending(true);
    setErrorMessage(null);
    try {
      const { a2ui_messages } = await apiClient.sendMessage(token, mensaje);
      processor.processMessages(a2ui_messages);
      setMensaje('');
    } catch (err) {
      handleApiError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-view">
      <header className="chat-header">
        <span>me-alcanza</span>
        <button type="button" onClick={logout}>
          Salir
        </button>
      </header>
      <main className="chat-surfaces">
        {surfaces.length === 0 && (
          <p className="chat-empty">Escribe tu primer mensaje para empezar.</p>
        )}
        {surfaces.map((surface) => (
          <A2uiSurface key={surface.id} surface={surface} />
        ))}
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
