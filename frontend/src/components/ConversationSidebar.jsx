import { formatFecha } from '../views/yo/formatters.js';

// Lista de conversaciones pasadas, tipo el panel lateral de ChatGPT/Claude:
// elegir una carga su historial (AsistenteView se encarga de eso) y "Nueva
// conversación" simplemente limpia la selección — el próximo mensaje que se
// mande, al no llevar conversacion_id, hace que el backend cree una
// conversación real (mismo camino que ya usa el primer mensaje de siempre).
export default function ConversationSidebar({ conversaciones, activeId, onSelect, onNueva }) {
  return (
    <nav className="conversation-sidebar" aria-label="Historial de conversaciones">
      <button type="button" className="conversation-nueva" onClick={onNueva}>
        + Nueva conversación
      </button>
      <ul className="conversation-list">
        {(conversaciones ?? []).map((conversacion) => (
          <li key={conversacion.id}>
            <button
              type="button"
              className={`conversation-item ${conversacion.id === activeId ? 'conversation-item-active' : ''}`}
              onClick={() => onSelect(conversacion.id)}
            >
              <span className="conversation-item-titulo">{conversacion.titulo}</span>
              <span className="conversation-item-fecha">{formatFecha(conversacion.updated_at?.slice(0, 10))}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
