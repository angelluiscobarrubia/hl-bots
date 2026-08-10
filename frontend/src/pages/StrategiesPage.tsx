import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

type StrategiesResp = {
  available: string[];
  count: number;
};

export default function StrategiesPage() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<StrategiesResp>({
    queryKey: ['strategies'],
    queryFn: async () => (await apiClient.get<StrategiesResp>('/strategies')).data,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Estrategias (plugins)</h1>
        <button
          className="btn btn-sm btn-outline"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          {isFetching ? 'Recargando…' : 'Recargar'}
        </button>
      </div>

      {isLoading && <div className="alert">Cargando…</div>}
      {isError && (
        <div className="alert alert-error">Error al listar estrategias.</div>
      )}

      {data && (
        <div className="overflow-x-auto">
          <table className="table table-zebra">
            <thead>
              <tr>
                <th>#</th>
                <th>Nombre</th>
                <th>Origen</th>
              </tr>
            </thead>
            <tbody>
              {data.available.map((name, i) => (
                <tr key={name}>
                  <td>{i + 1}</td>
                  <td className="font-mono">{name}</td>
                  <td className="opacity-60 text-sm">
                    strategies/{name.toLowerCase()}.py
                  </td>
                </tr>
              ))}
              {data.available.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-center opacity-60">
                    Ninguna estrategia registrada.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="alert alert-info text-sm">
        Añade un archivo <code className="font-mono">.py</code> en{' '}
        <code className="font-mono">backend/strategies/</code> que herede de{' '}
        <code className="font-mono">BaseStrategy</code>. El watcher lo detectará y
        aparecerá aquí tras pulsar <em>Recargar</em>.
      </div>
    </div>
  );
}
