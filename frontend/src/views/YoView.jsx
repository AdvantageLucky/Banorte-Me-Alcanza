import { useState } from 'react';
import CuentaTab from './yo/CuentaTab.jsx';
import TransaccionesTab from './yo/TransaccionesTab.jsx';
import MetasTab from './yo/MetasTab.jsx';
import ApartadosTab from './yo/ApartadosTab.jsx';
import PagosFijosTab from './yo/PagosFijosTab.jsx';
import IngresosTab from './yo/IngresosTab.jsx';
import ContactosTab from './yo/ContactosTab.jsx';

const SECCIONES = [
  { id: 'cuenta', label: 'Cuenta', Component: CuentaTab },
  { id: 'transacciones', label: 'Transacciones', Component: TransaccionesTab },
  { id: 'metas', label: 'Metas', Component: MetasTab },
  { id: 'apartados', label: 'Apartados', Component: ApartadosTab },
  { id: 'pagos-fijos', label: 'Pagos fijos', Component: PagosFijosTab },
  { id: 'ingresos', label: 'Ingresos', Component: IngresosTab },
  { id: 'contactos', label: 'Contactos', Component: ContactosTab },
];

export default function YoView() {
  const [activeId, setActiveId] = useState(SECCIONES[0].id);
  const activa = SECCIONES.find((seccion) => seccion.id === activeId);
  const ActiveComponent = activa.Component;

  return (
    <div className="yo-view">
      <nav className="yo-subnav" aria-label="Secciones de Yo">
        {SECCIONES.map((seccion) => (
          <button
            key={seccion.id}
            type="button"
            className={`yo-subnav-tab ${seccion.id === activeId ? 'yo-subnav-tab-active' : ''}`}
            onClick={() => setActiveId(seccion.id)}
          >
            {seccion.label}
          </button>
        ))}
      </nav>
      <div className="yo-content">
        <ActiveComponent />
      </div>
    </div>
  );
}
