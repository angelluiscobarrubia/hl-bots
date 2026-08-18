import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, type Mock } from 'vitest';
import LoginPage from '@/pages/LoginPage';
import { useAuthStore } from '@/store/authStore';

vi.mock('@/store/authStore', () => ({
  useAuthStore: {
    getState: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const getStateMock = useAuthStore.getState as Mock;

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders email and password inputs with submit button', () => {
    getStateMock.mockReturnValue({
      login: vi.fn(),
      mustChangePassword: false,
    });
    render(<LoginPage />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeInTheDocument();
  });

  it('calls login and navigates to / on success', async () => {
    const loginMock = vi.fn().mockResolvedValue(undefined);
    getStateMock.mockReturnValue({
      login: loginMock,
      mustChangePassword: false,
    });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'admin@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Contraseña'), {
      target: { value: 'secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith('admin@example.com', 'secret')
    );
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('shows error message on login failure', async () => {
    const loginMock = vi.fn().mockRejectedValue(new Error('fail'));
    getStateMock.mockReturnValue({
      login: loginMock,
      mustChangePassword: false,
    });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'admin@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Contraseña'), {
      target: { value: 'secret' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ingresar' }));
    await waitFor(() =>
      expect(
        screen.getByText('Credenciales inválidas. Intente nuevamente.')
      ).toBeInTheDocument()
    );
  });
});
