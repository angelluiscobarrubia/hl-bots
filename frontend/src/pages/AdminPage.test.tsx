import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import AdminPage from '@/pages/AdminPage';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
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
        <AdminPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra estado de carga inicialmente', () => {
    vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}) as any);
    renderWithProviders();
    expect(screen.getByText(/Cargando usuarios/i)).toBeInTheDocument();
  });

  it('renderiza tabla de usuarios cuando los datos cargan', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: [
        { id: 1, email: 'admin@example.com', role: 'admin', is_active: true, must_change_password: false },
        { id: 2, email: 'user1@example.com', role: 'user', is_active: true, must_change_password: false },
      ],
    } as any);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('users-table')).toBeInTheDocument();
    });
    expect(screen.getByText('admin@example.com')).toBeInTheDocument();
    expect(screen.getByText('user1@example.com')).toBeInTheDocument();
  });

  it('muestra error cuando falla la carga', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'));

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/Error al cargar usuarios/i)).toBeInTheDocument();
    });
  });

  it('abre formulario de creacion al hacer click en Nuevo usuario', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ data: [] } as any);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('toggle-create')).toBeInTheDocument();
    });

    screen.getByTestId('toggle-create').click();

    await waitFor(() => {
      expect(screen.getByTestId('create-form')).toBeInTheDocument();
    });
  });
});
