import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/store/authStore';

const baseURL = import.meta.env.VITE_API_URL ?? '/api';

export const apiClient = axios.create({
  baseURL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach Bearer token
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

// Response interceptor: 401 -> refresh -> retry once
apiClient.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const status = err.response?.status;
    const original = err.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;

    // Don't try to refresh for /auth/login or /auth/refresh itself
    const url = original?.url ?? '';
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh');

    if (status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const ok = await useAuthStore.getState().refresh();
      if (ok) {
        const newToken = useAuthStore.getState().accessToken;
        if (newToken) {
          original.headers.set('Authorization', `Bearer ${newToken}`);
        }
        return apiClient(original);
      }
    }

    console.error('[api]', status, url, err.message);
    return Promise.reject(err);
  },
);
