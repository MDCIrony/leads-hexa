import axios, { type AxiosRequestConfig } from 'axios';
import { clearToken, getToken } from '../session/token-storage';
import type { components } from './schema';

// baseURL empty: every call passes the full '/api/v1/...' path, the same
// string that indexes the generated schema types. Splitting the prefix
// between client and call would force reconstructing it just to type it.
export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Login has no token yet, but every other call needs one; reading it fresh
// per request (instead of once at client creation) picks up login/logout.
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
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
 * A 401 only means "your session expired" when the failing request actually
 * carried a token. POST /api/v1/agents from BootstrapPage gets a 401 too,
 * for the opposite reason — no admin is logged in yet, and the platform
 * already has one — with no token in storage to check. That's what keeps
 * this from hijacking it into "session expired".
 */
export function handleUnauthorizedResponse(error: unknown): Promise<never> {
  if (axios.isAxiosError(error) && error.response?.status === 401 && getToken()) {
    clearToken();
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
