import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL ?? '/api';

export const apiClient = axios.create({
  baseURL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.response.use(
  (r) => r,
  (err) => {
    // TODO: centralizar toast/notificación
    console.error('[api]', err?.response?.status, err?.config?.url, err?.message);
    return Promise.reject(err);
  },
);
