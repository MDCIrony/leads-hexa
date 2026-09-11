import { apiClient, loginRequest } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';

export type CurrentUser = components['schemas']['CurrentUserResponse'];
export type LoginResult = components['schemas']['LoginResponse'];
export type MfaRequired = { status: 'MFA_REQUIRED' };
export type LoginOutcome = (CurrentUser & { status?: never }) | MfaRequired;
export type MfaSetup = components['schemas']['MfaSetupResponse'];
export type MfaRecoveryCodes = components['schemas']['MfaRecoveryCodesResponse'];
export type OAuthProviders = components['schemas']['OAuthProvidersResponse'];
export type OAuthProvider = 'GOOGLE' | 'GITHUB';

export function isOAuthProvider(provider: string): provider is OAuthProvider {
  return provider === 'GOOGLE' || provider === 'GITHUB';
}

/** POST /auth/login: form-urlencoded, email in `username` — see api-client.loginRequest. */
export async function login(email: string, password: string): Promise<LoginResult> {
  const { data } = await loginRequest(email, password);
  return data;
}

export function isMfaRequired(result: LoginOutcome): result is MfaRequired {
  return result.status === 'MFA_REQUIRED';
}

export async function oauthProviders(): Promise<OAuthProviders> {
  const { data } = await apiClient.get<OAuthProviders>('/api/v1/auth/oauth/providers');
  return data;
}

export function oauthStartUrl(provider: OAuthProvider, returnPath: string): string {
  if (!isOAuthProvider(provider)) return '/';
  const safePath = /^\/(?!\/)[^?#\\\x00-\x1f\x7f]*$/.test(returnPath) ? returnPath : '/';
  return `/api/v1/auth/oauth/${provider.toLowerCase()}/start?${new URLSearchParams({ return_path: safePath })}`;
}

/** The only source of the role and identity: never read from the token. */
export async function me(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>('/api/v1/auth/me');
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/api/v1/auth/logout');
}

export async function verifyMfa(code: string): Promise<LoginResult> {
  const { data } = await apiClient.post<LoginResult>('/api/v1/auth/mfa/verify', { code });
  return data;
}

export async function setupMfa(password: string): Promise<MfaSetup> {
  const { data } = await apiClient.post<MfaSetup>('/api/v1/auth/mfa/setup', { password });
  return data;
}

export async function confirmMfa(code: string): Promise<MfaRecoveryCodes> {
  const { data } = await apiClient.post<MfaRecoveryCodes>('/api/v1/auth/mfa/setup/confirm', { code });
  return data;
}

export async function regenerateMfa(password: string, code: string): Promise<MfaRecoveryCodes> {
  const { data } = await apiClient.post<MfaRecoveryCodes>('/api/v1/auth/mfa/recovery-codes/regenerate', { password, code });
  return data;
}

export async function disableMfa(password: string, code: string): Promise<void> {
  await apiClient.post('/api/v1/auth/mfa/disable', { password, code });
}
