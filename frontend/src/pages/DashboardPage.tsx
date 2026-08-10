import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { useAppStore } from '@/store/appStore';
import { useEffect } from 'react';

type HealthResp = {
  status: string;
  service: string;
  version: string;
  strategies_available: string[];
};

export default function DashboardPage() {
  const setHealth = useAppStore((s) => s.setHealth);
  const { data, isLoading, isError } = useQuery<HealthResp>({
    queryKey: ['health'],
    queryFn: async () => (await apiClient.get<HealthResp>('/health')).data,
    refetchInterval: 10_000,
  });

  useEffect(() => {
    if (data) setHealth(data);
  }, [data, setHealth]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {isLoading && <div className="alert">Cargando…</div>}
      {isError && (
        <div className="alert alert-error">
          No se pudo conectar con el backend.
        </div>
      )}

      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card bg-base-200">
            <div className="card-body">
              <h2 className="card-title text-sm opacity-70">Estado</h2>
              <p className="text-2xl font-mono">
                <span className="badge badge-success">{data.status}</span>
              </p>
            </div>
          </div>
          <div className="card bg-base-200">
            <div className="card-body">
              <h2 className="card-title text-sm opacity-70">Servicio</h2>
              <p className="font-mono">{data.service}</p>
              <p className="text-xs opacity-60">v{data.version}</p>
            </div>
          </div>
          <div className="card bg-base-200">
            <div className="card-body">
              <h2 className="card-title text-sm opacity-70">
                Estrategias cargadas
              </h2>
              <p className="text-2xl font-mono">
                {data.strategies_available.length}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
