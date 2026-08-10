import axios, { type AxiosRequestConfig } from 'axios';

// baseURL empty: every call passes the full '/api/v1/...' path, the same
// string that indexes the generated schema types. Splitting the prefix
// between client and call would force reconstructing it just to type it.
export const apiClient = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * POST /api/v1/auth/login expects OAuth2PasswordRequestForm: form-urlencoded
 * body with the email in the 'username' field, not JSON. Sending JSON here
 * responds 422.
 */
export function loginRequest(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  return apiClient.post('/api/v1/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
}

/** POST /api/v1/intake/leads/batch-upload needs multipart, not the default JSON header. */
export function multipartConfig(): AxiosRequestConfig {
  return { headers: { 'Content-Type': 'multipart/form-data' } };
}
