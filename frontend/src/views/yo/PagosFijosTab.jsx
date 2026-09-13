import { apiClient } from '../../api/client.js';
import RecurrenteTab from './RecurrenteTab.jsx';

export default function PagosFijosTab() {
  return (
    <RecurrenteTab
      fetchFn={apiClient.getGastosFijos}
      createFn={apiClient.createGastoFijo}
      updateFn={apiClient.updateGastoFijo}
      deleteFn={apiClient.deleteGastoFijo}
      labelField="concepto"
      labelText="Concepto"
      emptyMessage="No tienes pagos fijos registrados."
    />
  );
}
