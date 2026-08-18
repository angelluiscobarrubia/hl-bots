import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useBotWebSocket } from '@/hooks/useWebSocket';
import { apiClient } from '@/services/api';

type Bot = {
  id: number;
  user_id: number;
  name: string;
  strategy_name: string;
  symbol: string;
  is_paper: boolean;
  status: 'stopped' | 'running' | 'paused' | 'error';
  created_at: string;
  updated_at: string;
};

type CreateBotBody = {
  name: string;
  strategy: string;
  symbol?: string;
  is_paper?: boolean;
  config?: Record<string, unknown>;
};

type StartBotBody = {
  api_key?: string;
  api_secret?: string;
};

type RiskStatus = {
  bot_id: number;
  starting_balance: number;
  current_balance: number;
  peak_balance: number;
  daily_pnl: number;
  drawdown_pct: number;
  open_positions: number;
  is_halted: boolean;
  halt_reason: string | null;
};

const STRATEGIES = ['sma_crossover', 'moving_average_crossover'];

function getErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? fallback;
}

function statusBadge(status: Bot['status']): string {
  switch (status) {
    case 'running':
      return 'badge-success';
    case 'paused':
      return 'badge-warning';
    case 'error':
      return 'badge-error';
    default:
      return 'badge-ghost';
  }
}

export default function BotsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newStrategy, setNewStrategy] = useState('sma_crossover');
  const [newSymbol, setNewSymbol] = useState('BTC-USD');
  const [newIsPaper, setNewIsPaper] = useState(true);
  const [startBotId, setStartBotId] = useState<number | null>(null);
  const [startApiKey, setStartApiKey] = useState('');
  const [startApiSecret, setStartApiSecret] = useState('');
  const [riskBotId, setRiskBotId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [haltAlert, setHaltAlert] = useState<{ botId: number; reason: string } | null>(null);

  useBotWebSocket((msg) => {
    if (msg.type === 'bot_status') {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
    } else if (msg.type === 'trade') {
      setToast(`Trade ${msg.trade.side} ${msg.trade.symbol} @ ${msg.trade.price}`);
      window.setTimeout(() => setToast(null), 4000);
    } else if (msg.type === 'risk_update') {
      queryClient.invalidateQueries({ queryKey: ['risk', msg.bot_id] });
    } else if (msg.type === 'risk_halt') {
      setHaltAlert({ botId: msg.bot_id, reason: msg.reason });
    }
  });

  const { data: bots, isLoading, isError, error } = useQuery<Bot[]>({
    queryKey: ['bots'],
    queryFn: async () => {
      const resp = await apiClient.get<{ bots: Bot[]; total: number }>('/bots');
      return resp.data.bots;
    },
  });

  const { data: riskStatus, isLoading: riskLoading, isError: riskError } = useQuery<RiskStatus>({
    queryKey: ['risk', riskBotId],
    queryFn: async () => {
      const resp = await apiClient.get<RiskStatus>(`/bots/${riskBotId}/risk/status`);
      return resp.data;
    },
    enabled: riskBotId !== null,
  });

  const createMutation = useMutation({
    mutationFn: async (body: CreateBotBody) => (await apiClient.post('/bots', body)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setShowCreate(false);
      setNewName('');
      setNewStrategy('sma_crossover');
      setNewSymbol('BTC-USD');
      setNewIsPaper(true);
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err, 'Error al crear bot'));
    },
  });

  const startMutation = useMutation({
    mutationFn: async ({ botId, body }: { botId: number; body: StartBotBody }) =>
      (await apiClient.post(`/bots/${botId}/start`, body)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setStartBotId(null);
      setStartApiKey('');
      setStartApiSecret('');
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err, 'Error al iniciar bot'));
    },
  });

  const stopMutation = useMutation({
    mutationFn: async (botId: number) => (await apiClient.post(`/bots/${botId}/stop`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] });
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err, 'Error al detener bot'));
    },
  });

  const haltMutation = useMutation({
    mutationFn: async (botId: number) => (await apiClient.post(`/bots/${botId}/risk/halt`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk', riskBotId] });
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err, 'Error al detener trading'));
    },
  });

  const resumeMutation = useMutation({
    mutationFn: async (botId: number) => (await apiClient.post(`/bots/${botId}/risk/resume`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk', riskBotId] });
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err, 'Error al reanudar trading'));
    },
  });

  const startBot = startBotId !== null ? bots?.find((b) => b.id === startBotId) : undefined;

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      name: newName,
      strategy: newStrategy,
      symbol: newSymbol,
      is_paper: newIsPaper,
    });
  };

  const handleStart = (e: React.FormEvent) => {
    e.preventDefault();
    if (startBotId === null) return;
    const body: StartBotBody = {};
    if (startBot && !startBot.is_paper) {
      body['api_key'] = startApiKey;
      body['api_secret'] = startApiSecret;
    }
    startMutation.mutate({ botId: startBotId, body });
  };

  const closeStartModal = () => {
    setStartBotId(null);
    setStartApiKey('');
    setStartApiSecret('');
  };

  const closeRiskModal = () => {
    setRiskBotId(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Bots</h1>
        <button
          className="btn btn-primary"
          onClick={() => setShowCreate(!showCreate)}
          data-testid="toggle-create"
        >
          {showCreate ? 'Cancelar' : 'Nuevo bot'}
        </button>
      </div>

      {actionError && (
        <div className="alert alert-error" data-testid="action-error">
          {actionError}
        </div>
      )}

      {toast && (
        <div className="alert alert-success" data-testid="trade-toast">
          {toast}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="card bg-base-200" data-testid="create-form">
          <div className="card-body space-y-3">
            <h2 className="card-title text-lg">Crear bot</h2>
            <input
              type="text"
              placeholder="Nombre"
              className="input input-bordered w-full"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
              data-testid="new-name"
            />
            <select
              className="select select-bordered w-full"
              value={newStrategy}
              onChange={(e) => setNewStrategy(e.target.value)}
              data-testid="new-strategy"
            >
              {STRATEGIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Símbolo (ej: BTC-USD)"
              className="input input-bordered w-full"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              data-testid="new-symbol"
            />
            <label className="label cursor-pointer justify-start gap-2">
              <input
                type="checkbox"
                className="checkbox checkbox-primary"
                checked={newIsPaper}
                onChange={(e) => setNewIsPaper(e.target.checked)}
                data-testid="new-is-paper"
              />
              <span className="label-text">Paper trading</span>
            </label>
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

      {isLoading && <div className="alert">Cargando bots…</div>}
      {isError && (
        <div className="alert alert-error">
          Error al cargar bots: {error?.message ?? 'desconocido'}
        </div>
      )}

      {bots && (
        <div className="overflow-x-auto">
          <table className="table table-zebra" data-testid="bots-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Estrategia</th>
                <th>Símbolo</th>
                <th>Modo</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((b) => (
                <tr key={b.id} data-testid={`bot-row-${b.id}`}>
                  <td>{b.name}</td>
                  <td>{b.strategy_name}</td>
                  <td>{b.symbol}</td>
                  <td>
                    <span className={`badge ${b.is_paper ? 'badge-info' : 'badge-warning'}`}>
                      {b.is_paper ? 'paper' : 'real'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${statusBadge(b.status)}`}>{b.status}</span>
                  </td>
                  <td className="space-x-2">
                    {b.status === 'stopped' && (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => {
                          setStartBotId(b.id);
                          setStartApiKey('');
                          setStartApiSecret('');
                        }}
                        data-testid={`start-${b.id}`}
                      >
                        Start
                      </button>
                    )}
                    {b.status === 'running' && (
                      <>
                        <button
                          className="btn btn-sm btn-warning"
                          onClick={() => stopMutation.mutate(b.id)}
                          disabled={stopMutation.isPending}
                          data-testid={`stop-${b.id}`}
                        >
                          Stop
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => setRiskBotId(b.id)}
                          data-testid={`risk-${b.id}`}
                        >
                          Risk
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {startBot && (
        <div className="modal modal-open" data-testid="start-modal">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Iniciar bot: {startBot.name}</h3>
            <form onSubmit={handleStart} className="mt-4 space-y-3">
              {!startBot.is_paper && (
                <>
                  <input
                    type="password"
                    placeholder="API Key"
                    className="input input-bordered w-full"
                    value={startApiKey}
                    onChange={(e) => setStartApiKey(e.target.value)}
                    required
                    data-testid="start-api-key"
                  />
                  <input
                    type="password"
                    placeholder="API Secret"
                    className="input input-bordered w-full"
                    value={startApiSecret}
                    onChange={(e) => setStartApiSecret(e.target.value)}
                    required
                    data-testid="start-api-secret"
                  />
                </>
              )}
              <div className="modal-action">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={startMutation.isPending}
                  data-testid="confirm-start"
                >
                  {startMutation.isPending ? 'Iniciando…' : 'Confirmar'}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={closeStartModal}
                  data-testid="cancel-start"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {riskBotId !== null && (
        <div className="modal modal-open" data-testid="risk-modal">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Estado de riesgo</h3>
            {riskLoading && <div className="alert mt-4">Cargando estado de riesgo…</div>}
            {riskError && (
              <div className="alert alert-error mt-4">Error al cargar estado de riesgo</div>
            )}
            {riskStatus && (
              <div className="mt-4 space-y-2">
                <div className="flex justify-between">
                  <span>Balance inicial</span>
                  <span data-testid="risk-starting-balance">
                    {riskStatus.starting_balance.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Balance actual</span>
                  <span data-testid="risk-current-balance">
                    {riskStatus.current_balance.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>P&L diario</span>
                  <span data-testid="risk-daily-pnl">{riskStatus.daily_pnl.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Drawdown</span>
                  <span data-testid="risk-drawdown">
                    {(riskStatus.drawdown_pct * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Posiciones abiertas</span>
                  <span data-testid="risk-open-positions">{riskStatus.open_positions}</span>
                </div>
                {riskStatus.is_halted && (
                  <div className="alert alert-warning mt-2">
                    Trading detenido: {riskStatus.halt_reason ?? 'sin motivo'}
                  </div>
                )}
                <div className="modal-action">
                  {riskStatus.is_halted ? (
                    <button
                      className="btn btn-success"
                      onClick={() => resumeMutation.mutate(riskBotId)}
                      disabled={resumeMutation.isPending}
                      data-testid="resume-bot"
                    >
                      Reanudar
                    </button>
                  ) : (
                    <button
                      className="btn btn-error"
                      onClick={() => haltMutation.mutate(riskBotId)}
                      disabled={haltMutation.isPending}
                      data-testid="halt-bot"
                    >
                      Detener trading
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={closeRiskModal}
                    data-testid="close-risk"
                  >
                    Cerrar
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {haltAlert && (
        <div className="modal modal-open" data-testid="halt-alert">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Trading detenido</h3>
            <p className="mt-2">
              El bot {haltAlert.botId} ha detenido el trading: {haltAlert.reason}
            </p>
            <div className="modal-action">
              <button
                className="btn btn-primary"
                onClick={() => setHaltAlert(null)}
                data-testid="close-halt-alert"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
