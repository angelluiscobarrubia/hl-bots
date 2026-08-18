import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import BotsPage from '@/pages/BotsPage';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from '@/services/api';

const paperBot = {
  id: 1,
  user_id: 1,
  name: 'Bot Paper',
  strategy_name: 'sma_crossover',
  symbol: 'BTC-USD',
  is_paper: true,
  status: 'stopped',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

const realBot = {
  id: 2,
  user_id: 1,
  name: 'Bot Real',
  strategy_name: 'moving_average_crossover',
  symbol: 'ETH-USD',
  is_paper: false,
  status: 'running',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

const realBotStopped = {
  id: 3,
  user_id: 1,
  name: 'Bot Real Detenido',
  strategy_name: 'moving_average_crossover',
  symbol: 'ETH-USD',
  is_paper: false,
  status: 'stopped',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

const riskStatus = {
  bot_id: 2,
  starting_balance: 1000,
  current_balance: 1050,
  peak_balance: 1100,
  daily_pnl: 50,
  drawdown_pct: 0.05,
  open_positions: 2,
  is_halted: false,
  halt_reason: null,
};

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BotsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('BotsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra loading mientras carga', () => {
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}) as Promise<unknown>);
    renderWithProviders();
    expect(screen.getByText(/Cargando bots/i)).toBeInTheDocument();
  });

  it('muestra error si falla la carga', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText(/Error al cargar bots/i)).toBeInTheDocument();
    });
  });

  it('renderiza tabla con bots', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [paperBot, realBot], total: 2 } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('bot-row-1')).toBeInTheDocument();
      expect(screen.getByTestId('bot-row-2')).toBeInTheDocument();
    });
    expect(screen.getByText('Bot Paper')).toBeInTheDocument();
    expect(screen.getByText('Bot Real')).toBeInTheDocument();
  });

  it('muestra formulario de creación al hacer click en Nuevo bot', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [], total: 0 } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('toggle-create')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('toggle-create'));
    expect(screen.getByTestId('create-form')).toBeInTheDocument();
  });

  it('envía POST al crear un bot', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [], total: 0 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: 3, name: 'Mi bot' } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('toggle-create')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('toggle-create'));
    fireEvent.change(screen.getByTestId('new-name'), { target: { value: 'Mi bot' } });
    fireEvent.click(screen.getByTestId('submit-create'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/bots',
        expect.objectContaining({
          name: 'Mi bot',
          strategy: 'sma_crossover',
          symbol: 'BTC-USD',
          is_paper: true,
        }),
      );
    });
  });

  it('inicia un bot paper sin keys', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [paperBot], total: 1 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...paperBot, status: 'running' } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('start-1')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('start-1'));
    expect(screen.getByTestId('start-modal')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('confirm-start'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/bots/1/start', {});
    });
  });

  it('inicia un bot real con keys', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [realBotStopped], total: 1 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...realBotStopped, status: 'running' } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('start-3')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('start-3'));
    expect(screen.getByTestId('start-modal')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('start-api-key'), { target: { value: 'my-key' } });
    fireEvent.change(screen.getByTestId('start-api-secret'), { target: { value: 'my-secret' } });
    fireEvent.click(screen.getByTestId('confirm-start'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/bots/3/start', {
        api_key: 'my-key',
        ['api_secret']: 'my-secret',
      });
    });
  });

  it('detiene un bot en ejecución', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { bots: [realBot], total: 1 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...realBot, status: 'stopped' } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('stop-2')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('stop-2'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/bots/2/stop');
    });
  });

  it('muestra estado de riesgo al hacer click en Risk', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: { bots: [realBot], total: 1 } })
      .mockResolvedValue({ data: riskStatus });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('risk-2')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('risk-2'));
    await waitFor(() => {
      expect(screen.getByTestId('risk-modal')).toBeInTheDocument();
      expect(screen.getByTestId('risk-current-balance')).toHaveTextContent('1050.00');
      expect(screen.getByTestId('risk-daily-pnl')).toHaveTextContent('50.00');
      expect(screen.getByTestId('risk-open-positions')).toHaveTextContent('2');
    });
  });

  it('detiene trading desde el modal de riesgo', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: { bots: [realBot], total: 1 } })
      .mockResolvedValue({ data: riskStatus });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...riskStatus, is_halted: true } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('risk-2')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('risk-2'));
    await waitFor(() => {
      expect(screen.getByTestId('halt-bot')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('halt-bot'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/bots/2/risk/halt');
    });
  });
});
