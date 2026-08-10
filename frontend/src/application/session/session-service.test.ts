import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const meMock = vi.fn();
const loginRequestMock = vi.fn();

vi.mock('../services/auth.service', () => ({
  me: meMock,
  login: loginRequestMock,
}));

// node environment has no localStorage; a Map-backed stub stands in for it,
// same approach as infrastructure/session/token-storage.test.ts.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear = () => this.store.clear();
  getItem = (key: string) => this.store.get(key) ?? null;
  key = (index: number) => Array.from(this.store.keys())[index] ?? null;
  removeItem = (key: string) => void this.store.delete(key);
  setItem = (key: string, value: string) => void this.store.set(key, value);
}

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage());
  meMock.mockReset();
  loginRequestMock.mockReset();
});

describe('login', () => {
  it('resolves the role from GET /auth/me, not from the token', async () => {
    const { login } = await import('./session-service');
    loginRequestMock.mockResolvedValue({ access_token: 'a-jwt', token_type: 'bearer' });
    meMock.mockResolvedValue({ id: '1', name: 'Ana', email: 'ana@acme.test', role: 'MANAGER' });

    const user = await login('ana@acme.test', 'secret');

    expect(user.role).toBe('MANAGER');
    expect(meMock).toHaveBeenCalled();
  });
});

describe('rehydrateSession', () => {
  it('discards an expired token on 401 and leaves the session anonymous', async () => {
    const { rehydrateSession } = await import('./session-service');
    localStorage.setItem('leads-hexa:access_token', 'stale-jwt');
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
    expect(localStorage.getItem('leads-hexa:access_token')).toBeNull();
  });
});
