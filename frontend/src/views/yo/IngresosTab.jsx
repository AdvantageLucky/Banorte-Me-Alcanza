import { apiClient } from '../../api/client.js';
import RecurrenteTab from './RecurrenteTab.jsx';

export default function IngresosTab() {
  return (
    <RecurrenteTab
      fetchFn={apiClient.getIngresosProgramados}
      labelField="descripcion"
      emptyMessage="No tienes ingresos programados."
    />
  );
}
