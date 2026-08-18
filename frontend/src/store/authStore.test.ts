import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the api module BEFORE importing the store
vi.mock('@/services/api', () => ({
  apiClient: {
    post: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}));

import { apiClient } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

describe('authStore', () => {
  beforeEach(() => {
    // Clear persist storage to avoid state leaking between tests
    useAuthStore.persist.clearStorage();
    // Reset store state
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      mustChangePassword: false,
    });
    vi.clearAllMocks();
  });

  it('login guarda tokens y user', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: 'A',
        refresh_token: 'R',
        token_type: 'bearer',
        user: { id: 1, email: 'a@b.com', role: 'user', is_active: true },
        must_change_password: false,
      },
    });

    await useAuthStore.getState().login('a@b.com', 'pw');

    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('A');
    expect(s.refreshToken).toBe('R');
    expect(s.user).toEqual({ id: 1, email: 'a@b.com', role: 'user', is_active: true });
    expect(s.mustChangePassword).toBe(false);
  });

  it('refresh con 200 actualiza tokens y devuelve true', async () => {
    useAuthStore.setState({ accessToken: 'OLD_A', refreshToken: 'OLD_R' });
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { access_token: 'NEW_A', refresh_token: 'NEW_R', token_type: 'bearer' },
    });

    const ok = await useAuthStore.getState().refresh();

    expect(ok).toBe(true);
    const s = useAuthStore.getState();
    expect(s.accessToken).toBe('NEW_A');
    expect(s.refreshToken).toBe('NEW_R');
  });

  it('refresh con 401 limpia estado y devuelve false', async () => {
    useAuthStore.setState({
      accessToken: 'A',
      refreshToken: 'R',
      user: { id: 1, email: 'a@b.com', role: 'user', is_active: true },
    });
    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('401'));

    const ok = await useAuthStore.getState().refresh();

    expect(ok).toBe(false);
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
  });

  it('logout limpia estado', () => {
    useAuthStore.setState({
      accessToken: 'A',
      refreshToken: 'R',
      user: { id: 1, email: 'a@b.com', role: 'user', is_active: true },
    });
    useAuthStore.getState().logout();
    const s = useAuthStore.getState();
    expect(s.accessToken).toBeNull();
    expect(s.refreshToken).toBeNull();
    expect(s.user).toBeNull();
  });
});
