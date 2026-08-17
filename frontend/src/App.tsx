import { Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';
import BotsPage from '@/pages/BotsPage';
import StrategiesPage from '@/pages/StrategiesPage';
import LoginPage from '@/pages/LoginPage';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuthStore } from '@/store/authStore';

export default function App() {
  const navigate = useNavigate();
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  const handleLogout = () => {
    useAuthStore.getState().logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-base-100">
      <header className="navbar bg-base-200 border-b border-base-300 px-6">
        <div className="flex-1">
          <span className="text-xl font-bold tracking-tight">HL Bots</span>
          <span className="ml-2 badge badge-ghost text-xs">v0.1.0</span>
        </div>
        {accessToken && (
          <>
            <nav className="flex gap-2">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`
                }
              >
                Dashboard
              </NavLink>
              <NavLink
                to="/bots"
                className={({ isActive }) =>
                  `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`
                }
              >
                Bots
              </NavLink>
              <NavLink
                to="/strategies"
                className={({ isActive }) =>
                  `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`
                }
              >
                Estrategias
              </NavLink>
            </nav>
            <div className="flex items-center gap-3 ml-4">
              {user && (
                <div className="flex items-center gap-2">
                  <span className="text-sm">{user.email}</span>
                  <span className="badge badge-primary badge-sm">{user.role}</span>
                </div>
              )}
              <button className="btn btn-sm btn-ghost" onClick={handleLogout}>
                Salir
              </button>
            </div>
          </>
        )}
      </header>
      <main className="container mx-auto p-6">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/bots"
            element={
              <ProtectedRoute>
                <BotsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/strategies"
            element={
              <ProtectedRoute>
                <StrategiesPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
