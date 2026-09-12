import { apiClient } from '../../api/client.js';
import { useApiResource } from '../../api/useApiResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

export default function TransaccionesTab() {
  const { token, logout } = useAuth();
  const { data: movimientos, loading, error, reload } = useApiResource(
    () => apiClient.getMovimientos(token),
    { onUnauthorized: logout },
  );

  return (
    <ResourceState
      loading={loading}
      error={error}
      reload={reload}
      isEmpty={!movimientos?.length}
      emptyMessage="Todavía no tienes movimientos."
    >
      <ul className="yo-list">
        {movimientos?.map((mov, index) => (
          <li key={`${mov.fecha}-${index}`} className="yo-card yo-movimiento">
            <div>
              <p className="yo-movimiento-concepto">{mov.concepto}</p>
              <p className="yo-movimiento-fecha">{formatFecha(mov.fecha)}</p>
            </div>
            <p className={`yo-monto ${mov.monto < 0 ? 'yo-monto-negativo' : 'yo-monto-positivo'}`}>
              {formatMonto(mov.monto)}
            </p>
          </li>
        ))}
      </ul>
    </ResourceState>
  );
}
