import axios from 'axios';
import { login as loginRequest, logout as logoutRequest, me as fetchCurrentUser, type LoginOutcome } from '../services/auth.service';
import type { CurrentUser } from '../services/auth.service';

export type { CurrentUser };

/**
 * Two-step login: POST /auth/login sets an HttpOnly cookie, never the role.
 * GET /auth/me is mandatory, not an optimization — it's the only source of
 * the role and identity that decide which panel the user lands on.
 */
export async function login(email: string, password: string): Promise<LoginOutcome> {
  const result = await loginRequest(email, password);
  if (result.status === 'MFA_REQUIRED') return { status: 'MFA_REQUIRED' };
  return fetchCurrentUser();
}

export async function logout(): Promise<void> {
  await logoutRequest();
}

/**
 * Restores the session on reload. A 401 means the cookie session expired.
 * silently, nobody is at fault for that. Any other failure bubbles up
 * instead of being mistaken for "not logged in".
 */
export async function rehydrateSession(): Promise<CurrentUser | null> {
  try {
    return await fetchCurrentUser();
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return null;
    }
    throw error;
  }
}
