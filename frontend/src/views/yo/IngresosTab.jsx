import { apiClient } from '../../api/client.js';
import RecurrenteTab from './RecurrenteTab.jsx';

export default function IngresosTab() {
  return (
    <RecurrenteTab
      fetchFn={apiClient.getIngresosProgramados}
      createFn={apiClient.createIngresoProgramado}
      updateFn={apiClient.updateIngresoProgramado}
      deleteFn={apiClient.deleteIngresoProgramado}
      labelField="descripcion"
      labelText="Descripción"
      emptyMessage="No tienes ingresos programados."
    />
  );
}
