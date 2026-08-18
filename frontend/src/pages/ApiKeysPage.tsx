import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/services/api';

type ApiKey = {
  id: number;
  user_id: number;
  bot_id: string;
  exchange: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type CreateApiKeyBody = {
  user_id: number;
  bot_id: string;
  exchange: string;
  api_key: string;
  secret: string;
};

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newUserId, setNewUserId] = useState('1');
  const [newBotId, setNewBotId] = useState('');
  const [newExchange, setNewExchange] = useState('hyperliquid');
  const [newApiKey, setNewApiKey] = useState('');
  const [newSecret, setNewSecret] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: keys, isLoading, isError, error } = useQuery<ApiKey[]>({
    queryKey: ['admin-api-keys'],
    queryFn: async () => {
      const resp = await apiClient.get<{ keys: ApiKey[]; total: number }>('/admin/api-keys');
      return resp.data.keys;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (body: CreateApiKeyBody) =>
      (await apiClient.post('/admin/api-keys', body)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] });
      setShowCreate(false);
      setNewBotId('');
      setNewApiKey('');
      setNewSecret('');
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(err?.response?.data?.detail ?? 'Error al crear API key');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: async (botId: string) =>
      (await apiClient.post(`/admin/api-keys/${botId}/deactivate`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-api-keys'] });
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(err?.response?.data?.detail ?? 'Error al desactivar API key');
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      user_id: parseInt(newUserId, 10),
      bot_id: newBotId,
      exchange: newExchange,
      api_key: newApiKey,
      secret: newSecret,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">API Keys de Exchanges</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreate(!showCreate)}
          data-testid="toggle-create"
        >
          {showCreate ? 'Cancelar' : 'Nueva API key'}
        </button>
      </div>

      <div className="alert alert-info text-sm">
        Las API keys se cifran con Fernet antes de guardarse. El plaintext nunca
        se almacena ni se devuelve en respuestas.
      </div>

      {actionError && (
        <div className="alert alert-error" data-testid="action-error">
          {actionError}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="card bg-base-200" data-testid="create-form">
          <div className="card-body space-y-3">
            <h2 className="card-title text-lg">Crear API key</h2>
            <input
              type="number"
              placeholder="User ID"
              className="input input-bordered w-full"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              min={1}
              required
              data-testid="new-user-id"
            />
            <input
              type="text"
              placeholder="Bot ID (ej: bot-001)"
              className="input input-bordered w-full"
              value={newBotId}
              onChange={(e) => setNewBotId(e.target.value)}
              required
              data-testid="new-bot-id"
            />
            <select
              className="select select-bordered w-full"
              value={newExchange}
              onChange={(e) => setNewExchange(e.target.value)}
              data-testid="new-exchange"
            >
              <option value="hyperliquid">hyperliquid</option>
            </select>
            <input
              type="password"
              placeholder="API Key"
              className="input input-bordered w-full"
              value={newApiKey}
              onChange={(e) => setNewApiKey(e.target.value)}
              required
              data-testid="new-api-key"
            />
            <input
              type="password"
              placeholder="API Secret"
              className="input input-bordered w-full"
              value={newSecret}
              onChange={(e) => setNewSecret(e.target.value)}
              required
              data-testid="new-secret"
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending}
              data-testid="submit-create"
            >
              {createMutation.isPending ? 'Creando…' : 'Crear'}
            </button>
          </div>
        </form>
      )}

      {isLoading && <div className="alert">Cargando API keys…</div>}
      {isError && (
        <div className="alert alert-error">
          Error al cargar API keys: {(error as unknown)?.message ?? 'desconocido'}
        </div>
      )}

      {keys && (
        <div className="overflow-x-auto">
          <table className="table table-zebra" data-testid="keys-table">
            <thead>
              <tr>
                <th>Bot ID</th>
                <th>User ID</th>
                <th>Exchange</th>
                <th>Activo</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} data-testid={`key-row-${k.bot_id}`}>
                  <td>{k.bot_id}</td>
                  <td>{k.user_id}</td>
                  <td>
                    <span className="badge badge-ghost">{k.exchange}</span>
                  </td>
                  <td>
                    <span className={`badge ${k.is_active ? 'badge-success' : 'badge-error'}`}>
                      {k.is_active ? 'sí' : 'no'}
                    </span>
                  </td>
                  <td>
                    {k.is_active && (
                      <button
                        className="btn btn-sm btn-warning"
                        onClick={() => deactivateMutation.mutate(k.bot_id)}
                        disabled={deactivateMutation.isPending}
                        data-testid={`deactivate-${k.bot_id}`}
                      >
                        Desactivar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
