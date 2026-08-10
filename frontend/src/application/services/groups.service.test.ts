import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import groupsPage from '../../test/fixtures/groups-page.json';
import { create, list, remove } from './groups.service';

describe('groups.list', () => {
  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/groups': { data: groupsPage } });

    const page = await list(20, 0);

    expect(page.total).toBe(groupsPage.total);
    expect(page.items[0].name).toBe(groupsPage.items[0].name);
  });
});

describe('groups.create and groups.remove', () => {
  it('creates and deletes without reshaping the payload', async () => {
    const groupId = groupsPage.items[0].id;
    mockApiClient({
      'POST /api/v1/groups': { status: 201, data: groupsPage.items[0] },
      [`DELETE /api/v1/groups/${groupId}`]: { status: 204, data: undefined },
    });

    const group = await create({ name: 'Ventas Norte', default_strategy: 'LOWEST_LOAD' });
    expect(group.id).toBe(groupId);

    await expect(remove(group.id)).resolves.toBeUndefined();
  });
});
