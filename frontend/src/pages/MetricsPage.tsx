import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { apiClient } from '@/services/api';

type Metrics = {
  bot_id: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  max_win: number;
  max_loss: number;
  sharpe_ratio: number | null;
  starting_balance: number;
  current_balance: number;
};

type Trade = {
  id: number;
  bot_id: number;
  symbol: string;
  side: string;
  price: number;
  quantity: number;
  pnl: number;
  executed_at: string;
};

type EquityPoint = {
  timestamp: string;
  equity: number;
};

type Bot = {
  id: number;
  user_id: number;
  name: string;
  strategy_name: string;
  symbol: string;
  is_paper: boolean;
  status: string;
  created_at: string;
  updated_at: string;
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function formatPnl(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
}

function pnlClass(value: number): string {
  if (value > 0) return 'text-success';
  if (value < 0) return 'text-error';
  return '';
}

export default function MetricsPage() {
  const { id } = useParams<{ id: string }>();
  const botId = Number(id);
  const navigate = useNavigate();

  const { data: bot, isLoading: botLoading, isError: botError } = useQuery<Bot>({
    queryKey: ['bot', botId],
    queryFn: async () => (await apiClient.get<Bot>(`/bots/${botId}`)).data,
    enabled: Number.isFinite(botId),
  });

  const { data: metrics, isLoading: metricsLoading, isError: metricsError } = useQuery<Metrics>({
    queryKey: ['metrics', botId],
    queryFn: async () => (await apiClient.get<Metrics>(`/bots/${botId}/metrics`)).data,
    enabled: Number.isFinite(botId),
  });

  const { data: trades, isLoading: tradesLoading, isError: tradesError } = useQuery<Trade[]>({
    queryKey: ['trades', botId],
    queryFn: async () =>
      (await apiClient.get<Trade[]>(`/bots/${botId}/trades`, { params: { limit: 20 } })).data,
    enabled: Number.isFinite(botId),
  });

  const { data: equity, isLoading: equityLoading, isError: equityError } = useQuery<EquityPoint[]>({
    queryKey: ['equity', botId],
    queryFn: async () =>
      (await apiClient.get<EquityPoint[]>(`/bots/${botId}/equity-curve`)).data,
    enabled: Number.isFinite(botId),
  });

  const loading = botLoading || metricsLoading || tradesLoading || equityLoading;
  const error = botError || metricsError || tradesError || equityError;

  const pnlDistribution = metrics
    ? [
        { name: 'Ganadoras', value: metrics.winning_trades },
        { name: 'Perdedoras', value: metrics.losing_trades },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => navigate('/bots')}
            data-testid="back-button"
          >
            ← Volver
          </button>
          <h1 className="text-2xl font-bold" data-testid="metrics-title">
            {bot ? bot.name : 'Métricas'}
          </h1>
        </div>
      </div>

      {loading && <div className="alert">Cargando métricas…</div>}
      {error && (
        <div className="alert alert-error" data-testid="metrics-error">
          Error al cargar métricas
        </div>
      )}

      {metrics && metrics.total_trades === 0 && (
        <div className="alert" data-testid="empty-state">
          Este bot aún no tiene trades registrados.
        </div>
      )}

      {metrics && metrics.total_trades > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card bg-base-200" data-testid="summary-total-pnl">
              <div className="card-body">
                <h2 className="card-title text-sm opacity-70">P&L total</h2>
                <p className={`text-2xl font-mono ${pnlClass(metrics.total_pnl)}`}>
                  {formatPnl(metrics.total_pnl)}
                </p>
              </div>
            </div>
            <div className="card bg-base-200" data-testid="summary-win-rate">
              <div className="card-body">
                <h2 className="card-title text-sm opacity-70">Win rate</h2>
                <p className="text-2xl font-mono">{(metrics.win_rate * 100).toFixed(1)}%</p>
              </div>
            </div>
            <div className="card bg-base-200" data-testid="summary-total-trades">
              <div className="card-body">
                <h2 className="card-title text-sm opacity-70">Trades</h2>
                <p className="text-2xl font-mono">{metrics.total_trades}</p>
              </div>
            </div>
            <div className="card bg-base-200" data-testid="summary-sharpe">
              <div className="card-body">
                <h2 className="card-title text-sm opacity-70">Sharpe ratio</h2>
                <p className="text-2xl font-mono">
                  {metrics.sharpe_ratio !== null ? metrics.sharpe_ratio.toFixed(2) : '—'}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card bg-base-200" data-testid="equity-chart">
              <div className="card-body">
                <h2 className="card-title text-lg">Curva de equity</h2>
                {equity && equity.length > 0 ? (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={equity} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="timestamp" tickFormatter={formatTime} />
                        <YAxis />
                        <Tooltip labelFormatter={formatTime} />
                        <Line
                          type="monotone"
                          dataKey="equity"
                          stroke="#8884d8"
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="opacity-60">Sin datos de equity.</p>
                )}
              </div>
            </div>

            <div className="card bg-base-200" data-testid="pnl-distribution">
              <div className="card-body">
                <h2 className="card-title text-lg">Distribución de P&L</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={pnlDistribution} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#8884d8" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          <div className="card bg-base-200">
            <div className="card-body">
              <h2 className="card-title text-lg">Trades recientes</h2>
              {trades && trades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="table table-zebra" data-testid="trades-table">
                    <thead>
                      <tr>
                        <th>Símbolo</th>
                        <th>Lado</th>
                        <th>Precio</th>
                        <th>Cantidad</th>
                        <th>P&L</th>
                        <th>Fecha</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((t) => (
                        <tr key={t.id} data-testid={`trade-row-${t.id}`}>
                          <td>{t.symbol}</td>
                          <td>
                            <span
                              className={`badge ${t.side === 'buy' ? 'badge-info' : 'badge-warning'}`}
                            >
                              {t.side}
                            </span>
                          </td>
                          <td className="font-mono">{t.price.toFixed(2)}</td>
                          <td className="font-mono">{t.quantity.toFixed(4)}</td>
                          <td className={`font-mono ${pnlClass(t.pnl)}`}>{formatPnl(t.pnl)}</td>
                          <td>{formatTime(t.executed_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="opacity-60">Sin trades recientes.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
