import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MetricsPage from '@/pages/MetricsPage';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

import { apiClient } from '@/services/api';

const bot = {
  id: 1,
  user_id: 1,
  name: 'Bot Alpha',
  strategy_name: 'sma_crossover',
  symbol: 'BTC-USD',
  is_paper: true,
  status: 'running',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

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

const metrics: Metrics = {
  bot_id: 1,
  total_trades: 3,
  winning_trades: 2,
  losing_trades: 1,
  win_rate: 2 / 3,
  total_pnl: 12.0,
  avg_pnl: 4.0,
  max_win: 10.0,
  max_loss: -4.0,
  sharpe_ratio: 1.5,
  starting_balance: 0.0,
  current_balance: 12.0,
};

const emptyMetrics: Metrics = {
  bot_id: 1,
  total_trades: 0,
  winning_trades: 0,
  losing_trades: 0,
  win_rate: 0,
  total_pnl: 0,
  avg_pnl: 0,
  max_win: 0,
  max_loss: 0,
  sharpe_ratio: null,
  starting_balance: 0,
  current_balance: 0,
};

const trades = [
  {
    id: 1,
    bot_id: 1,
    symbol: 'BTC-USD',
    side: 'buy',
    price: 50000,
    quantity: 0.1,
    pnl: 10,
    executed_at: '2026-01-01T12:00:00Z',
  },
  {
    id: 2,
    bot_id: 1,
    symbol: 'BTC-USD',
    side: 'sell',
    price: 51000,
    quantity: 0.1,
    pnl: -4,
    executed_at: '2026-01-01T13:00:00Z',
  },
];

const equity = [
  { timestamp: '2026-01-01T12:00:00Z', equity: 10 },
  { timestamp: '2026-01-01T13:00:00Z', equity: 6 },
];

function mockApi(data: {
  bot?: typeof bot;
  metrics?: typeof metrics;
  trades?: typeof trades;
  equity?: typeof equity;
}) {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/metrics')) {
      return Promise.resolve({ data: data.metrics ?? metrics });
    }
    if (url.includes('/trades')) {
      return Promise.resolve({ data: data.trades ?? trades });
    }
    if (url.includes('/equity-curve')) {
      return Promise.resolve({ data: data.equity ?? equity });
    }
    return Promise.resolve({ data: data.bot ?? bot });
  });
}

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/bots/1/metrics']}>
        <Routes>
          <Route path="/bots/:id/metrics" element={<MetricsPage />} />
          <Route path="/bots" element={<div>Bots list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('MetricsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra loading mientras carga', () => {
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}) as Promise<unknown>);
    renderWithProviders();
    expect(screen.getByText(/Cargando métricas/i)).toBeInTheDocument();
  });

  it('muestra error si falla la carga', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('metrics-error')).toBeInTheDocument();
    });
  });

  it('renderiza las tarjetas de resumen', async () => {
    mockApi({});
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('summary-total-pnl')).toBeInTheDocument();
    });
    expect(screen.getByTestId('summary-total-pnl')).toHaveTextContent('+12.00');
    expect(screen.getByTestId('summary-win-rate')).toHaveTextContent('66.7%');
    expect(screen.getByTestId('summary-total-trades')).toHaveTextContent('3');
    expect(screen.getByTestId('summary-sharpe')).toHaveTextContent('1.50');
  });

  it('renderiza la curva de equity', async () => {
    mockApi({});
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('equity-chart')).toBeInTheDocument();
    });
    expect(screen.getByText('Curva de equity')).toBeInTheDocument();
  });

  it('renderiza la distribución de P&L', async () => {
    mockApi({});
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('pnl-distribution')).toBeInTheDocument();
    });
    expect(screen.getByText('Distribución de P&L')).toBeInTheDocument();
  });

  it('renderiza la tabla de trades recientes', async () => {
    mockApi({});
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('trades-table')).toBeInTheDocument();
    });
    expect(screen.getByTestId('trade-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('trade-row-2')).toBeInTheDocument();
    expect(screen.getAllByText('BTC-USD').length).toBeGreaterThan(0);
  });

  it('navega de vuelta al hacer click en Volver', async () => {
    mockApi({});
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('back-button')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('back-button'));
    await waitFor(() => {
      expect(screen.getByText('Bots list')).toBeInTheDocument();
    });
  });

  it('muestra estado vacío cuando no hay trades', async () => {
    mockApi({ metrics: emptyMetrics, trades: [], equity: [] });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
  });
});
