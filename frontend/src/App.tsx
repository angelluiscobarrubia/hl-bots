import { Routes, Route, NavLink } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';
import BotsPage from '@/pages/BotsPage';
import StrategiesPage from '@/pages/StrategiesPage';

export default function App() {
  return (
    <div className="min-h-screen bg-base-100">
      <header className="navbar bg-base-200 border-b border-base-300 px-6">
        <div className="flex-1">
          <span className="text-xl font-bold tracking-tight">HL Bots</span>
          <span className="ml-2 badge badge-ghost text-xs">v0.1.0</span>
        </div>
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
      </header>
      <main className="container mx-auto p-6">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/bots" element={<BotsPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
        </Routes>
      </main>
    </div>
  );
}
