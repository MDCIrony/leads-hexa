import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearToken, setToken } from '../session/token-storage';
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
    clearToken();
    setSessionExpiredListener(null);
  });

  it('clears the token and notifies the session when a request that carried one gets a 401', async () => {
    setToken('a-jwt');
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    await expect(handleUnauthorizedResponse(axiosErrorWith(401))).rejects.toBeInstanceOf(AxiosError);

    expect(listener).toHaveBeenCalledOnce();
  });

  // The trap: POST /api/v1/agents from BootstrapPage also answers 401 once
  // the platform already has an admin — that means "bootstrap is closed",
  // not "your session expired", and it fires with no token in storage.
  it('leaves an unauthenticated 401 alone, so it never reads as a session that expired', async () => {
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    await expect(handleUnauthorizedResponse(axiosErrorWith(401))).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });

  it('ignores non-401 errors entirely', async () => {
    setToken('a-jwt');
    const listener = vi.fn();
    setSessionExpiredListener(listener);

    await expect(handleUnauthorizedResponse(axiosErrorWith(500))).rejects.toBeInstanceOf(AxiosError);

    expect(listener).not.toHaveBeenCalled();
  });
});
