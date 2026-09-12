import { AuthProvider, useAuth } from './auth/AuthContext.jsx';
import LoginView from './views/LoginView.jsx';
import AppShell from './views/AppShell.jsx';

function AuthGate() {
  const { token } = useAuth();
  return token ? <AppShell /> : <LoginView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
