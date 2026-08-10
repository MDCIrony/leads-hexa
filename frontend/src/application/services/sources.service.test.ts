import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import type { components } from '../../infrastructure/api/schema';
import { create, list, remove } from './sources.service';

// No captured fixture for sources exists yet — typed literal against LeadSourceResponse.
const sourcesPage: components['schemas']['PaginatedSourcesResponse'] = {
  items: [
    {
      id: 'b2b2b2b2-0000-0000-0000-000000000001',
      name: 'Formulario manual',
      kind: 'MANUAL_FORM',
      field_mapping: {},
      is_active: true,
      created_at: '2026-08-10T19:01:07.777632+00:00',
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
  has_more: false,
};

describe('sources.list', () => {
  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/sources': { data: sourcesPage } });

    const page = await list(20, 0);

    expect(page.total).toBe(1);
    expect(page.items[0].kind).toBe('MANUAL_FORM');
  });
});

describe('sources.create and sources.remove', () => {
  it('creates and deletes without reshaping the payload', async () => {
    mockApiClient({
      'POST /api/v1/sources': { status: 201, data: sourcesPage.items[0] },
      'DELETE /api/v1/sources/b2b2b2b2-0000-0000-0000-000000000001': { status: 204, data: undefined },
    });

    const source = await create({ name: 'Formulario manual', kind: 'MANUAL_FORM' });
    expect(source.id).toBe('b2b2b2b2-0000-0000-0000-000000000001');

    await expect(remove(source.id)).resolves.toBeUndefined();
  });
});
