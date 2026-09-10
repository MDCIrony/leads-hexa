import { apiClient, loginRequest } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';

export type CurrentUser = components['schemas']['CurrentUserResponse'];
export type LoginResult = components['schemas']['LoginResponse'];

/** POST /auth/login: form-urlencoded, email in `username` — see api-client.loginRequest. */
export async function login(email: string, password: string): Promise<LoginResult> {
  const { data } = await loginRequest(email, password);
  return data;
}

/** The only source of the role and identity: never read from the token. */
export async function me(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>('/api/v1/auth/me');
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/api/v1/auth/logout');
}
