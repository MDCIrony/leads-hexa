import axios, { type AxiosRequestConfig } from 'axios';
import type { components } from './schema';

// baseURL empty: every call passes the full '/api/v1/...' path, the same
// string that indexes the generated schema types. Splitting the prefix
// between client and call would force reconstructing it just to type it.
export const apiClient = axios.create({
  baseURL: '',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

let sessionExpiredListener: (() => void) | null = null;

/** SessionProvider registers itself here; it's the only reader. */
export function setSessionExpiredListener(listener: (() => void) | null): void {
  sessionExpiredListener = listener;
}

/**
 * Exported (not inlined in the interceptor) so it can be tested without
 * driving a real request through axios.
 *
 * A 401 on an authenticated request removes the browser session state.
 */
export function handleUnauthorizedResponse(error: unknown): Promise<never> {
  const url = axios.isAxiosError(error) ? error.config?.url : undefined;
  if (
    axios.isAxiosError(error) &&
    error.response?.status === 401 &&
    url !== '/api/v1/auth/login' &&
    url !== '/api/v1/auth/mfa/verify'
  ) {
    sessionExpiredListener?.();
  }
  return Promise.reject(error);
}

apiClient.interceptors.response.use((response) => response, handleUnauthorizedResponse);

/**
 * POST /api/v1/auth/login expects OAuth2PasswordRequestForm: form-urlencoded
 * body with the email in the 'username' field, not JSON. Sending JSON here
 * responds 422.
 */
export function loginRequest(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  return apiClient.post<components['schemas']['LoginResponse']>('/api/v1/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

/** POST /api/v1/intake/leads/batch-upload needs multipart, not the default JSON header. */
export function multipartConfig(): AxiosRequestConfig {
  return { headers: { 'Content-Type': 'multipart/form-data' } };
}
