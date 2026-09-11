import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const meMock = vi.fn();
const loginRequestMock = vi.fn();
const logoutMock = vi.fn();

vi.mock('../services/auth.service', () => ({
  me: meMock,
  login: loginRequestMock,
  logout: logoutMock,
}));

beforeEach(() => {
  meMock.mockReset();
  loginRequestMock.mockReset();
  logoutMock.mockReset();
});

describe('login', () => {
  it('resolves the role from GET /auth/me, not from the login response', async () => {
    const { login } = await import('./session-service');
    loginRequestMock.mockResolvedValue({ status: 'AUTHENTICATED' });
    meMock.mockResolvedValue({ id: '1', name: 'Ana', email: 'ana@acme.test', role: 'MANAGER' });

    const user = await login('ana@acme.test', 'secret');

    expect(user.status).toBeUndefined();
    if (user.status === 'MFA_REQUIRED') throw new Error('Expected an authenticated user');
    expect(user.role).toBe('MANAGER');
    expect(meMock).toHaveBeenCalled();
  });
});

describe('rehydrateSession', () => {
  it('treats an expired cookie session as anonymous', async () => {
    const { rehydrateSession } = await import('./session-service');
    meMock.mockRejectedValue(
      new AxiosError('Unauthorized', '401', undefined, undefined, {
        status: 401,
        statusText: 'Unauthorized',
        headers: new AxiosHeaders(),
        config: { headers: new AxiosHeaders() },
        data: undefined,
      })
    );

    const user = await rehydrateSession();

    expect(user).toBeNull();
  });
});
