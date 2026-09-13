import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import AsistenteView from './AsistenteView.jsx';
import YoView from './YoView.jsx';

// Navbar de nivel app: antes ChatView era la única pantalla tras el login y
// traía su propio encabezado con marca + "Salir". Ahora ese encabezado vive
// aquí, una sola vez, con tabs para cambiar entre Asistente y Yo.
// El tab "Dashboard" (lista estática de sugerencias en HTML aparte, sin
// nada que la disparara sola) se eliminó: las sugerencias pendientes ahora
// se inyectan como tarjetas A2UI más en el mismo feed de Asistente (ver
// AsistenteView), con el mismo catálogo visual que cualquier respuesta del
// chat en vez de un componente de React aparte.
const TABS = [
  { id: 'asistente', label: 'Asistente' },
  { id: 'yo', label: 'Yo' },
];

const VIEWS = {
  asistente: AsistenteView,
  yo: YoView,
};

export default function AppShell() {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState('asistente');
  const ActiveView = VIEWS[activeTab];

  return (
    <div className="app-shell">
      <header className="app-navbar">
        <span className="app-navbar-brand">
          <span>Banorte</span>
          <span className="app-navbar-tagline"> — ¿Me Alcanza?</span>
        </span>
        <nav className="app-navbar-tabs" aria-label="Secciones">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`app-navbar-tab ${tab.id === activeTab ? 'app-navbar-tab-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <button
          type="button"
          className="app-navbar-tab logout"
          onClick={logout}
        >
          Salir
        </button>
      </header>
      <main className="app-shell-body">
        <ActiveView />
      </main>
    </div>
  );
}
