import { apiClient } from '../../api/client.js';
import RecurrenteTab from './RecurrenteTab.jsx';

export default function PagosFijosTab() {
  return (
    <RecurrenteTab
      fetchFn={apiClient.getGastosFijos}
      labelField="concepto"
      emptyMessage="No tienes pagos fijos registrados."
    />
  );
}
