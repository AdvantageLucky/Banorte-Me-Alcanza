import { apiClient } from '../../api/client.js';
import { useApiResource } from '../../api/useApiResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

export default function MetasTab() {
  const { token, logout } = useAuth();
  const { data: metas, loading, error, reload } = useApiResource(
    () => apiClient.getMetas(token),
    { onUnauthorized: logout },
  );

  return (
    <ResourceState
      loading={loading}
      error={error}
      reload={reload}
      isEmpty={!metas?.length}
      emptyMessage="Todavía no tienes metas de ahorro."
    >
      <ul className="yo-list">
        {metas?.map((meta) => {
          const progreso = meta.monto_objetivo > 0
            ? Math.min(100, Math.round((meta.monto_ahorrado / meta.monto_objetivo) * 100))
            : 0;
          return (
            <li key={meta.id} className="yo-card yo-meta">
              <p className="yo-meta-descripcion">{meta.descripcion}</p>
              <div className="yo-meta-progreso-track">
                <div className="yo-meta-progreso-fill" style={{ width: `${progreso}%` }} />
              </div>
              <p className="yo-meta-montos">
                {formatMonto(meta.monto_ahorrado)} de {formatMonto(meta.monto_objetivo)}
              </p>
              <p className="yo-meta-fecha">Meta: {formatFecha(meta.fecha_objetivo)}</p>
            </li>
          );
        })}
      </ul>
    </ResourceState>
  );
}
