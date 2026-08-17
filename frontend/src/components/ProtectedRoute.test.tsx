import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, type Mock } from 'vitest';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuthStore } from '@/store/authStore';

vi.mock('@/store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

const useAuthStoreMock = useAuthStore as unknown as Mock;

describe('ProtectedRoute', () => {
  it('redirects to /login when no token', () => {
    useAuthStoreMock.mockImplementation((selector) =>
      selector({ accessToken: null })
    );
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Login Page')).toBeInTheDocument();
  });

  it('renders children when token exists', () => {
    useAuthStoreMock.mockImplementation((selector) =>
      selector({ accessToken: 'token' })
    );
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });
});
