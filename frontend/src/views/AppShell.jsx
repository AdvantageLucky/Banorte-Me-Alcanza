import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import ChatView from './ChatView.jsx';
import DashboardView from './DashboardView.jsx';
import YoView from './YoView.jsx';

// Navbar de nivel app: antes ChatView era la única pantalla tras el login y
// traía su propio encabezado con marca + "Salir". Ahora ese encabezado vive
// aquí, una sola vez, con tabs para cambiar entre Dashboard, Chat y Yo.
const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'chat', label: 'Chat' },
  { id: 'yo', label: 'Yo' },
];

const VIEWS = {
  dashboard: DashboardView,
  chat: ChatView,
  yo: YoView,
};

export default function AppShell() {
  const { logout } = useAuth();
  // Chat sigue siendo la pantalla inicial al entrar, aunque Dashboard
  // aparezca primero en la barra (mismo orden que el shell de Flutter).
  const [activeTab, setActiveTab] = useState('chat');
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
