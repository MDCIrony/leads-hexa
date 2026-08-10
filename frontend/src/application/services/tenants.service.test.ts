import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import tenantsPageFixture from '../../test/fixtures/tenants-page.json';
import { apiClient } from '../../infrastructure/api/api-client';
import { create, list } from './tenants.service';

describe('tenants.list', () => {
  it('returns the paginated envelope intact, without flattening total or has_more', async () => {
    mockApiClient({ 'GET /api/v1/tenants': { data: tenantsPageFixture } });

    const page = await list(5, 0);

    expect(page.total).toBe(239);
    expect(page.has_more).toBe(true);
    expect(page.items).toHaveLength(5);
  });
});

describe('tenants.create', () => {
  it('nests the manager under `manager`, not as a root-level manager_email field', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: tenantsPageFixture.items[0],
      status: 201,
      statusText: '',
      headers: new AxiosHeaders(),
      config: { headers: new AxiosHeaders() },
    });

    await create({ name: 'Acme', manager: { name: 'Ana', email: 'ana@acme.test', password: 'secret123' } });

    const [, body] = postSpy.mock.calls[0];
    expect(body).toMatchObject({
      name: 'Acme',
      manager: { name: 'Ana', email: 'ana@acme.test', password: 'secret123' },
    });
    expect((body as Record<string, unknown>).manager_email).toBeUndefined();
  });
});
