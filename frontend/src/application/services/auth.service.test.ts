import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import loginFixture from '../../test/fixtures/login.json';
import meAdminFixture from '../../test/fixtures/me-admin.json';
import { login, me } from './auth.service';

describe('auth.login', () => {
  it('sends form-urlencoded with the email in username, never JSON — the most likely regression here', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: loginFixture,
      status: 200,
      statusText: '',
      headers: new AxiosHeaders(),
      config: { headers: new AxiosHeaders() },
    });

    await login('root@plat.test', 'Secret123');

    const [url, body, config] = postSpy.mock.calls[0];
    expect(url).toBe('/api/v1/auth/login');
    expect(config?.headers).toMatchObject({ 'Content-Type': 'application/x-www-form-urlencoded' });
    expect(body).toBeInstanceOf(URLSearchParams);
    expect((body as URLSearchParams).get('username')).toBe('root@plat.test');
    expect((body as URLSearchParams).get('email')).toBeNull();
  });
});

describe('auth.me', () => {
  it('resolves the role from the response body', async () => {
    mockApiClient({ 'GET /api/v1/auth/me': { data: meAdminFixture } });

    const user = await me();

    expect(user.role).toBe('ADMIN');
  });
});
