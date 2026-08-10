import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import type { components } from '../../infrastructure/api/schema';
import { create, list, remove } from './groups.service';

// No captured fixture for groups exists yet (src/test/fixtures/) — this literal is
// typed against PaginatedGroupsResponse so a contract change still breaks the build.
const groupsPage: components['schemas']['PaginatedGroupsResponse'] = {
  items: [
    {
      id: 'a1a1a1a1-0000-0000-0000-000000000001',
      name: 'Ventas Norte',
      description: null,
      default_strategy: 'LOWEST_LOAD',
      capacity_per_agent: null,
      is_active: true,
      agent_count: 2,
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
  has_more: false,
};

describe('groups.list', () => {
  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/groups': { data: groupsPage } });

    const page = await list(20, 0);

    expect(page.total).toBe(1);
    expect(page.items[0].name).toBe('Ventas Norte');
  });
});

describe('groups.create and groups.remove', () => {
  it('creates and deletes without reshaping the payload', async () => {
    mockApiClient({
      'POST /api/v1/groups': { status: 201, data: groupsPage.items[0] },
      'DELETE /api/v1/groups/a1a1a1a1-0000-0000-0000-000000000001': { status: 204, data: undefined },
    });

    const group = await create({ name: 'Ventas Norte', default_strategy: 'LOWEST_LOAD' });
    expect(group.id).toBe('a1a1a1a1-0000-0000-0000-000000000001');

    await expect(remove(group.id)).resolves.toBeUndefined();
  });
});
