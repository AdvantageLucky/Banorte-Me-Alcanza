import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import AsistenteView from './AsistenteView.jsx';
import YoView from './YoView.jsx';

// Navbar de nivel app: antes ChatView era la única pantalla tras el login y
// traía su propio encabezado con marca + "Salir". Ahora ese encabezado vive
// aquí, una sola vez, con tabs para cambiar entre Asistente y Yo.
// El tab "Dashboard" (lista estática de sugerencias, sin nada que la
// disparara sola) se eliminó: su contenido (NotificacionesPanel) ahora vive
// dentro de Asistente, donde sí se muestra sin que el usuario tenga que ir a
// buscarlo.
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
