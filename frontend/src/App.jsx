import { AuthProvider, useAuth } from './auth/AuthContext.jsx';
import LoginView from './views/LoginView.jsx';
import ChatView from './views/ChatView.jsx';

function AppShell() {
  const { token } = useAuth();
  return token ? <ChatView /> : <LoginView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
