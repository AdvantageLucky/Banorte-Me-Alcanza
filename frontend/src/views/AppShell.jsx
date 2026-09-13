import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import AsistenteView from './AsistenteView.jsx';
import AtencionView from './AtencionView.jsx';
import YoView from './YoView.jsx';
import { LogOut } from 'lucide-react';

// Navbar de nivel app: antes ChatView era la única pantalla tras el login y
// traía su propio encabezado con marca + "Salir". Ahora ese encabezado vive
// aquí, una sola vez, con tabs para cambiar entre Asistente, Atención y Yo.
// El tab "Dashboard" original (lista estática de sugerencias en HTML aparte,
// sin nada que la disparara sola) se eliminó; las notificaciones pasaron
// primero al feed de Asistente y ahora viven en su propio tab "Atención"
// (ver AtencionView), donde se pueden filtrar y cada una trae su propia UI
// generativa además de una propuesta del asistente bajo demanda.
const TABS = [
  { id: 'asistente', label: 'Asistente' },
  { id: 'atencion', label: 'Atención' },
  { id: 'yo', label: 'Yo' },
];

const VIEWS = {
  asistente: AsistenteView,
  atencion: AtencionView,
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
          <LogOut size={22} color="white" />
        </button>
      </header>
      <main className="app-shell-body">
        <ActiveView />
      </main>
    </div>
  );
}
