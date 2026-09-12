import { useState } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';
import ChatView from './ChatView.jsx';
import YoView from './YoView.jsx';

// Navbar de nivel app: antes ChatView era la única pantalla tras el login y
// traía su propio encabezado con marca + "Salir". Ahora ese encabezado vive
// aquí, una sola vez, con tabs para cambiar entre Chat y Yo.
const TABS = [
  { id: 'chat', label: 'Chat' },
  { id: 'yo', label: 'Yo' },
];

export default function AppShell() {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState(TABS[0].id);

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
        <button type="button" className="app-navbar-logout" onClick={logout}>
          Salir
        </button>
      </header>
      <main className="app-shell-body">
        {activeTab === 'chat' ? <ChatView /> : <YoView />}
      </main>
    </div>
  );
}
