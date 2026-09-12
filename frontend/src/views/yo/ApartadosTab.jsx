import { apiClient } from '../../api/client.js';
import { useApiResource } from '../../api/useApiResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

export default function ApartadosTab() {
  const { token, logout } = useAuth();
  const { data: apartados, loading, error, reload } = useApiResource(
    () => apiClient.getApartados(token),
    { onUnauthorized: logout },
  );

  return (
    <ResourceState
      loading={loading}
      error={error}
      reload={reload}
      isEmpty={!apartados?.length}
      emptyMessage="No tienes apartados automáticos configurados."
    >
      <ul className="yo-list">
        {apartados?.map((apartado) => (
          <li key={apartado.id} className="yo-card yo-apartado">
            <div>
              <p className="yo-apartado-monto">{formatMonto(apartado.monto_por_periodo)} / {apartado.periodicidad}</p>
              <p className="yo-apartado-detalle">Meta #{apartado.meta_id} · desde {formatFecha(apartado.fecha_inicio)}</p>
            </div>
            <span className={`yo-badge yo-badge-${apartado.estado}`}>{apartado.estado}</span>
          </li>
        ))}
      </ul>
    </ResourceState>
  );
}
