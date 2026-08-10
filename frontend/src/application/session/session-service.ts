import axios from 'axios';
import { login as loginRequest, me as fetchCurrentUser } from '../services/auth.service';
import { clearToken, getToken, setToken } from '../../infrastructure/session/token-storage';
import type { CurrentUser } from '../services/auth.service';

export type { CurrentUser };

/**
 * Two-step login: POST /auth/login returns only the token, never the role.
 * GET /auth/me is mandatory, not an optimization — it's the only source of
 * the role and identity that decide which panel the user lands on.
 */
export async function login(email: string, password: string): Promise<CurrentUser> {
  const { access_token } = await loginRequest(email, password);
  setToken(access_token);
  return fetchCurrentUser();
}

export function logout(): void {
  clearToken();
}

/**
 * Restores the session on reload. A 401 means the token expired: discarded
 * silently, nobody is at fault for that. Any other failure bubbles up
 * instead of being mistaken for "not logged in".
 */
export async function rehydrateSession(): Promise<CurrentUser | null> {
  const token = getToken();
  if (!token) {
    return null;
  }
  try {
    return await fetchCurrentUser();
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearToken();
      return null;
    }
    throw error;
  }
}
