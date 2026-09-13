import { useState } from 'react';
import { apiClient } from '../api/client.js';
import { useApiResource } from '../api/useApiResource.js';
import { useAuth } from '../auth/AuthContext.jsx';
import ResourceState from '../views/yo/ResourceState.jsx';
import { formatFecha } from '../views/yo/formatters.js';
import { getSugerenciaCopy } from '../views/notificaciones/sugerenciaCopy.js';

const FILTROS = [
  { id: 'pendientes', label: 'Pendientes', match: (s) => s.estado === 'pendiente' },
  { id: 'historial', label: 'Historial', match: (s) => s.estado !== 'pendiente' },
  { id: 'todas', label: 'Todas', match: () => true },
];

const EMPTY_MESSAGE = {
  pendientes: 'No tienes alertas pendientes por ahora.',
  historial: 'Todavía no has atendido ni descartado ninguna alerta.',
  todas: 'No tienes alertas por ahora.',
};

// Antes vivía en su propia pestaña ("Dashboard"), separada del chat y de
// cualquier otra pantalla — nada la disparaba sola ni la ponía frente al
// usuario sin que él fuera a buscarla. Ahora se monta directamente en el
// Asistente: se autocarga al entrar (useApiResource, sin esperar un mensaje)
// y ocupa la parte prominente de la pantalla, como notificaciones que
// requieren acción, no una lista que hay que ir a revisar.
export default function NotificacionesPanel() {
  const { token, logout } = useAuth();
  const [filtroId, setFiltroId] = useState(FILTROS[0].id);
  const [actingId, setActingId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const { data: sugerencias, loading, error, reload } = useApiResource(
    () => apiClient.getSugerencias(token),
    { onUnauthorized: logout },
  );

  async function handleAccion(sugerenciaId, accion) {
    setActingId(sugerenciaId);
    setActionError(null);
    try {
      const llamada = accion === 'atender' ? apiClient.atenderSugerencia : apiClient.descartarSugerencia;
      await llamada(token, sugerenciaId);
      await reload();
    } catch (err) {
      if (err?.status === 401) {
        logout();
        return;
      }
      setActionError(err?.detail || 'No se pudo actualizar la sugerencia, intenta de nuevo.');
    } finally {
      setActingId(null);
    }
  }

  const filtro = FILTROS.find((f) => f.id === filtroId);
  const visibles = sugerencias?.filter(filtro.match) ?? [];
  const pendientesCount = sugerencias?.filter((s) => s.estado === 'pendiente').length ?? 0;

  return (
    <section className="notificaciones-panel" aria-label="Notificaciones de IA">
      <div className="notificaciones-header">
        <h2 className="notificaciones-titulo">
          Notificaciones
          {pendientesCount > 0 && <span className="notificaciones-badge">{pendientesCount}</span>}
        </h2>
        <nav className="dashboard-filters" aria-label="Filtro de sugerencias">
          {FILTROS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`dashboard-filter-tab ${f.id === filtroId ? 'dashboard-filter-tab-active' : ''}`}
              onClick={() => setFiltroId(f.id)}
            >
              {f.label}
            </button>
          ))}
        </nav>
      </div>
      {actionError && <p className="yo-state-error">{actionError}</p>}
      <ResourceState
        loading={loading}
        error={error}
        reload={reload}
        isEmpty={visibles.length === 0}
        emptyMessage={EMPTY_MESSAGE[filtroId]}
      >
        <ul className="dashboard-feed">
          {visibles.map((sugerencia) => {
            const { titulo, descripcion } = getSugerenciaCopy(sugerencia);
            const enProceso = actingId === sugerencia.id;
            return (
              <li key={sugerencia.id} className={`sugerencia-card sugerencia-card-${sugerencia.estado}`}>
                <div className="sugerencia-card-body">
                  <p className="sugerencia-titulo">{titulo}</p>
                  <p className="sugerencia-descripcion">{descripcion}</p>
                  {sugerencia.estado !== 'pendiente' && (
                    <p className="sugerencia-resuelta">
                      {sugerencia.estado === 'atendida' ? 'Atendida' : 'Descartada'} el {formatFecha(sugerencia.resuelta_at?.slice(0, 10))}
                    </p>
                  )}
                </div>
                {sugerencia.estado === 'pendiente' && (
                  <div className="sugerencia-actions">
                    <button type="button" disabled={enProceso} onClick={() => handleAccion(sugerencia.id, 'atender')}>
                      Atender
                    </button>
                    <button
                      type="button"
                      className="sugerencia-actions-secundaria"
                      disabled={enProceso}
                      onClick={() => handleAccion(sugerencia.id, 'descartar')}
                    >
                      Descartar
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </ResourceState>
    </section>
  );
}
