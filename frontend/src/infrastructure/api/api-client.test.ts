import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { handleUnauthorizedResponse, setSessionExpiredListener } from './api-client';

function axiosErrorWith(status: number): AxiosError {
  return new AxiosError('failed', String(status), undefined, undefined, {
    status,
    statusText: '',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
    data: { error: true, error_code: 'UNAUTHORIZED', message: 'Not authenticated' },
  });
}

describe('handleUnauthorizedResponse', () => {
  beforeEach(() => {
    setSessionExpiredListener(null);
  });

  it('notifies the session when an authenticated request gets a 401', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    await expect(handleUnauthorizedResponse(axiosErrorWith(401))).rejects.toBeInstanceOf(AxiosError);

    expect(listener).toHaveBeenCalledOnce();
  });

  it('leaves login failures alone', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    const error = axiosErrorWith(401);
    Object.defineProperty(error, 'config', { value: { url: '/api/v1/auth/login' } });
    await expect(handleUnauthorizedResponse(error)).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });

  it('leaves session rehydration failures alone so an MFA challenge is not logged out', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    const error = axiosErrorWith(401);
    Object.defineProperty(error, 'config', { value: { url: '/api/v1/auth/me' } });
    await expect(handleUnauthorizedResponse(error)).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });

  it('leaves MFA verification failures alone so a wrong code does not discard the challenge', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    const error = axiosErrorWith(401);
    Object.defineProperty(error, 'config', { value: { url: '/api/v1/auth/mfa/verify' } });
    await expect(handleUnauthorizedResponse(error)).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });

  it.each([
    '/api/v1/auth/mfa/setup',
    '/api/v1/auth/mfa/setup/confirm',
    '/api/v1/auth/mfa/recovery-codes/regenerate',
    '/api/v1/auth/mfa/disable',
  ])('leaves %s failures alone so a wrong factor does not log out', async (url) => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    const error = axiosErrorWith(401);
    Object.defineProperty(error, 'config', { value: { url } });
    await expect(handleUnauthorizedResponse(error)).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });

  it('ignores non-401 errors entirely', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    await expect(handleUnauthorizedResponse(axiosErrorWith(500))).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });
});
