import { describe, it, expect } from 'vitest';
import { apiClient } from '@/services/api';

describe('apiClient', () => {
  it('se exporta correctamente con interceptors', () => {
    expect(apiClient).toBeDefined();
    expect(apiClient.interceptors).toBeDefined();
    expect(apiClient.interceptors.request).toBeDefined();
    expect(apiClient.interceptors.request.use).toBeDefined();
    expect(apiClient.interceptors.response).toBeDefined();
    expect(apiClient.interceptors.response.use).toBeDefined();
  });
});
