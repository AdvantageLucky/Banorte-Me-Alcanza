import { useApiResource } from '../../api/useApiResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

// Pagos fijos e ingresos programados comparten exactamente la misma forma
// ({concepto|descripcion, monto, frecuencia, proxima_fecha}) — una sola
// pestaña genérica evita duplicar el mismo card dos veces.
export default function RecurrenteTab({ fetchFn, labelField, emptyMessage }) {
  const { token, logout } = useAuth();
  const { data: items, loading, error, reload } = useApiResource(
    () => fetchFn(token),
    { onUnauthorized: logout },
  );

  return (
    <ResourceState
      loading={loading}
      error={error}
      reload={reload}
      isEmpty={!items?.length}
      emptyMessage={emptyMessage}
    >
      <ul className="yo-list">
        {items?.map((item) => (
          <li key={item.id} className="yo-card yo-recurrente">
            <div>
              <p className="yo-recurrente-label">{item[labelField]}</p>
              <p className="yo-recurrente-detalle">{item.frecuencia} · próxima: {formatFecha(item.proxima_fecha)}</p>
            </div>
            <p className="yo-monto">{formatMonto(item.monto)}</p>
          </li>
        ))}
      </ul>
    </ResourceState>
  );
}
