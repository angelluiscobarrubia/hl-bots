import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ApiKeysPage from '@/pages/ApiKeysPage';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from '@/services/api';

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ApiKeysPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra loading mientras carga', () => {
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}) as Promise<unknown>);
    renderWithProviders();
    expect(screen.getByText(/Cargando API keys/i)).toBeInTheDocument();
  });

  it('muestra error si falla la carga', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByText(/Error al cargar API keys/i)).toBeInTheDocument();
    });
  });

  it('renderiza tabla con API keys', async () => {
    const mockKeys = [
      { id: 1, user_id: 1, bot_id: 'bot-001', exchange: 'hyperliquid', is_active: true, created_at: '2026-01-01', updated_at: '2026-01-01' },
      { id: 2, user_id: 1, bot_id: 'bot-002', exchange: 'hyperliquid', is_active: false, created_at: '2026-01-01', updated_at: '2026-01-01' },
    ];
    vi.mocked(apiClient.get).mockResolvedValue({ data: { keys: mockKeys, total: 2 } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('key-row-bot-001')).toBeInTheDocument();
      expect(screen.getByTestId('key-row-bot-002')).toBeInTheDocument();
    });
  });

  it('muestra formulario de creación al hacer click en Nueva API key', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { keys: [], total: 0 } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('toggle-create')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('toggle-create'));
    expect(screen.getByTestId('create-form')).toBeInTheDocument();
  });

  it('envía POST al crear una API key', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { keys: [], total: 0 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: 1, bot_id: 'bot-new' } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('toggle-create')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('toggle-create'));
    fireEvent.change(screen.getByTestId('new-bot-id'), { target: { value: 'bot-new' } });
    fireEvent.change(screen.getByTestId('new-api-key'), { target: { value: 'my-key' } });
    fireEvent.change(screen.getByTestId('new-secret'), { target: { value: 'my-secret' } });
    fireEvent.click(screen.getByTestId('submit-create'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/admin/api-keys', expect.objectContaining({
        bot_id: 'bot-new',
        api_key: 'my-key',
        secret: 'my-secret',
      }));
    });
  });

  it('desactiva una API key al hacer click en Desactivar', async () => {
    const mockKeys = [
      { id: 1, user_id: 1, bot_id: 'bot-001', exchange: 'hyperliquid', is_active: true, created_at: '2026-01-01', updated_at: '2026-01-01' },
    ];
    vi.mocked(apiClient.get).mockResolvedValue({ data: { keys: mockKeys, total: 1 } });
    vi.mocked(apiClient.post).mockResolvedValue({ data: { ...mockKeys[0], is_active: false } });
    renderWithProviders();
    await waitFor(() => {
      expect(screen.getByTestId('deactivate-bot-001')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('deactivate-bot-001'));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/admin/api-keys/bot-001/deactivate');
    });
  });
});
