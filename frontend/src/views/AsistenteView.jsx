import { useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface } from '@a2ui/react/v0_9';
import { injectStyles, removeStyles } from '@a2ui/react/styles';
// injectStyles() (arriba) solo trae el CSS estructural heredado de v0_8
// (layout de los wrappers .a2ui-surface .a2ui-*). Las clases reales del
// catálogo básico v0_9 (.button, .primary, .a2uiText, etc.) viven en este
// archivo estático y nadie las importaba, por lo que Button/Text/TextField/
// ChoicePicker se renderizaban sin ningún estilo.
import '@a2ui/react/v0_9/index.css';
import { meAlcanzaCatalog } from '../a2ui-custom/catalog.js';
import '../a2ui-custom/styles.css';
import { apiClient } from '../api/client.js';
import { useApiResource } from '../api/useApiResource.js';
import { createActionHandler } from '../chat/actionHandler.js';
import { createConfirmActionWithModal } from '../chat/confirmWithModal.js';
import { buildTurnsFromHistorial } from '../chat/buildTurnsFromHistorial.js';
import { dropDuplicateCreateSurface } from '../chat/messageFilter.js';
import { extractSurfaceId } from '../chat/extractSurfaceId.js';
import Typewriter from '../components/typewritter.jsx';
import ConfirmActionModal from '../components/ConfirmActionModal.jsx';
import ConversationSidebar from '../components/ConversationSidebar.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import logo from '../assets/images/logo.svg';

// Las notificaciones/sugerencias ya no viven aquí: tienen su propio tab
// "Atención" (ver AtencionView), donde se pueden filtrar y cada una trae su
// propia UI generativa más una propuesta del asistente bajo demanda. Este
// componente vuelve a ser solo el chat.
export default function AsistenteView() {
  const { token, logout } = useAuth();
  const [mensaje, setMensaje] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  // Transcripción de la conversación activa: cada turno queda como su propia
  // entrada (nunca se sobrescribe uno anterior), en el orden real en que
  // ocurrieron — el backend le da a cada turno del agente su propio
  // surfaceId único (tanto en vivo como al reabrir un historial pasado).
  const [turns, setTurns] = useState([]);
  // null = todavía no hay conversación real: el próximo mensaje que se
  // mande hace que el backend cree una y devuelva su id (ver handleSubmit).
  const [conversacionId, setConversacionId] = useState(null);
  // Confirmación pendiente antes de ejecutar confirmar_accion (ver
  // confirmActionWithModal más abajo): { resumen, onConfirm, onCancel }.
  const [pendingConfirmation, setPendingConfirmation] = useState(null);

  const { data: conversaciones, reload: reloadConversaciones } = useApiResource(
    () => apiClient.getConversaciones(token),
    { onUnauthorized: logout },
  );

  function handleApiError(err, fallback) {
    if (err?.silent) {
      // Cancelado por el usuario en el modal de confirmación: no es un error.
      return;
    }
    if (err?.status === 401) {
      logout();
      return;
    }
    setErrorMessage(err?.detail || fallback);
  }

  const confirmActionWithModal = useMemo(
    () =>
      createConfirmActionWithModal({
        getPropuesta: (proposalId) => apiClient.getPropuesta(token, proposalId),
        confirmAction: (proposalId) => apiClient.confirmAction(token, proposalId),
        requestConfirmation: (payload) => setPendingConfirmation(payload),
      }),
    [token],
  );

  function appendAgentTurn(messages) {
    const surfaceId = extractSurfaceId(messages);
    if (surfaceId) {
      setTurns((prev) => [...prev, { kind: 'agent', id: surfaceId, surfaceId }]);
    }
  }

  const processor = useMemo(() => {
    let proc;
    const confirmActionHandler = createActionHandler({
      confirmAction: confirmActionWithModal,
      onMessages: (messages) => {
        setErrorMessage(null);
        proc.processMessages(
          dropDuplicateCreateSurface(messages, new Set(proc.model.surfacesMap.keys())),
        );
        appendAgentTurn(messages);
      },
      onError: (err) => handleApiError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
    });
    proc = new MessageProcessor([meAlcanzaCatalog], confirmActionHandler);
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
      const { a2ui_messages, conversacion_id: nuevoConversacionId } = await apiClient.sendMessage(
        token,
        texto,
        conversacionId,
      );
      // Se captura SIEMPRE (haya sido autocreada en este mensaje o ya
      // existiera): sin esto, el siguiente mensaje se manda de nuevo sin
      // conversacion_id y el backend crea otra conversación distinta en
      // cada turno — la memoria de contexto nunca llega a usarse aunque
      // esté completamente implementada del lado del backend.
      setConversacionId(nuevoConversacionId);
      processor.processMessages(
        dropDuplicateCreateSurface(a2ui_messages, new Set(processor.model.surfacesMap.keys())),
      );
      appendAgentTurn(a2ui_messages);
      reloadConversaciones();
    } catch (err) {
      handleApiError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      setSending(false);
    }
  }

  function handleNuevaConversacion() {
    setConversacionId(null);
    setTurns([]);
    setErrorMessage(null);
  }

  async function handleSelectConversacion(id) {
    if (id === conversacionId) {
      return;
    }
    setErrorMessage(null);
    try {
      const mensajes = await apiClient.getMensajesConversacion(token, id);
      const loadedTurns = buildTurnsFromHistorial(mensajes, {
        processMessages: (a2uiJson) =>
          processor.processMessages(
            dropDuplicateCreateSurface(a2uiJson, new Set(processor.model.surfacesMap.keys())),
          ),
        extractSurfaceId,
      });
      setTurns(loadedTurns);
      setConversacionId(id);
    } catch (err) {
      handleApiError(err, 'No se pudo cargar el historial de esta conversación.');
    }
  }

  return (
    <div className="asistente-view">
      <ConversationSidebar
        conversaciones={conversaciones}
        activeId={conversacionId}
        onSelect={handleSelectConversacion}
        onNueva={handleNuevaConversacion}
      />
      <div className="chat-view">
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
            if (turn.kind === 'agent-text') {
              return (
                <div className="chat-bot" key={turn.id}>
                  <img className="chat-logo" src={logo} alt="Logo" width="40" height="40" />
                  <p className="chat-message-agent-text">{turn.text}</p>
                </div>
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
      {pendingConfirmation && (
        <ConfirmActionModal
          resumen={pendingConfirmation.resumen}
          onConfirm={() => {
            setPendingConfirmation(null);
            pendingConfirmation.onConfirm();
          }}
          onCancel={() => {
            setPendingConfirmation(null);
            pendingConfirmation.onCancel();
          }}
        />
      )}
    </div>
  );
}
