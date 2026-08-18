import { Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import DashboardPage from '@/pages/DashboardPage';
import BotsPage from '@/pages/BotsPage';
import StrategiesPage from '@/pages/StrategiesPage';
import LoginPage from '@/pages/LoginPage';
import AdminPage from '@/pages/AdminPage';
import ApiKeysPage from '@/pages/ApiKeysPage';
import ProtectedRoute from '@/components/ProtectedRoute';

export default function App() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-base-100">
      <header className="navbar bg-base-200 border-b border-base-300 px-6">
        <div className="flex-1">
          <span className="text-xl font-bold tracking-tight">HL Bots</span>
          <span className="ml-2 badge badge-ghost text-xs">v0.1.0</span>
        </div>
        {user && (
          <nav className="flex gap-2 items-center">
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
            {user.role === 'admin' && (
              <>
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`
                  }
                  data-testid="admin-navlink"
                >
                  Admin
                </NavLink>
                <NavLink
                  to="/admin/api-keys"
                  className={({ isActive }) =>
                    `btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`
                  }
                  data-testid="api-keys-navlink"
                >
                  API Keys
                </NavLink>
              </>
            )}
            <div className="divider divider-horizontal mx-0"></div>
            <span className="text-sm opacity-70" data-testid="user-email">{user.email}</span>
            <span className={`badge ${user.role === 'admin' ? 'badge-primary' : 'badge-ghost'}`} data-testid="user-role">
              {user.role}
            </span>
            <button
              className="btn btn-sm btn-ghost"
              onClick={handleLogout}
              data-testid="logout-btn"
            >
              Logout
            </button>
          </nav>
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
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/api-keys"
            element={
              <ProtectedRoute>
                <ApiKeysPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
