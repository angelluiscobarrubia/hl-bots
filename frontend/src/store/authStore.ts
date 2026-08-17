import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiClient } from '@/services/api';

export type AuthUser = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
};

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  mustChangePassword: boolean,
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<boolean>;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: AuthUser | null) => void;
  setMustChangePassword: (v: boolean) => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      mustChangePassword: false,

      login: async (email, password) => {
        const { data } = await apiClient.post('/auth/login', { email, password });
        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          user: data.user,
          mustChangePassword: data.must_change_password,
        });
      },

      logout: () => {
        set({ accessToken: null, refreshToken: null, user: null, mustChangePassword: false });
      },

      refresh: async () => {
        const refreshToken = get().refreshToken;
        if (!refreshToken) return false;
        try {
          const { data } = await apiClient.post('/auth/refresh', { refresh_token: refreshToken });
          set({ accessToken: data.access_token, refreshToken: data.refresh_token });
          return true;
        } catch {
          set({ accessToken: null, refreshToken: null, user: null, mustChangePassword: false });
          return false;
        }
      },

      setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh }),
      setUser: (user) => set({ user }),
      setMustChangePassword: (v) => set({ mustChangePassword: v }),
    }),
    {
      name: 'hl-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    },
  ),
);
