import { apiClient } from '../../api/client.js';
import { useApiResource } from '../../api/useApiResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatMonto } from './formatters.js';

export default function CuentaTab() {
  const { token, logout } = useAuth();
  const { data: cuenta, loading, error, reload } = useApiResource(
    () => apiClient.getCuenta(token),
    { onUnauthorized: logout },
  );

  return (
    <ResourceState
      loading={loading}
      error={error}
      reload={reload}
      isEmpty={!cuenta}
      emptyMessage="No encontramos información de tu cuenta."
    >
      {cuenta && (
        <div className="yo-card yo-cuenta-card">
          <p className="yo-cuenta-titular">{cuenta.titular}</p>
          <p className="yo-cuenta-numero">Cuenta {cuenta.numero_cuenta}</p>
          <p className="yo-cuenta-saldo">{formatMonto(cuenta.saldo, cuenta.moneda)}</p>
        </div>
      )}
    </ResourceState>
  );
}
