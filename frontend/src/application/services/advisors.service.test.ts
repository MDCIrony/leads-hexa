import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import advisorsPageFixture from '../../test/fixtures/advisors-page.json';
import groupsPageFixture from '../../test/fixtures/groups-page.json';
import { list, setGroup } from './advisors.service';

const [groupedAdvisor] = advisorsPageFixture.items;
const [fixtureGroup] = groupsPageFixture.items;

describe('advisors.list', () => {
  afterEach(() => vi.restoreAllMocks());

  it('filters a group through /advisors and leaves is_active out, so inactive members come too', async () => {
    mockApiClient({ 'GET /api/v1/advisors': { data: advisorsPageFixture } });

    const page = await list(20, 0, { groupId: fixtureGroup.id });

    const params = vi.mocked(apiClient.get).mock.calls[0][1]?.params as Record<string, unknown>;
    expect(params).toMatchObject({ group_id: fixtureGroup.id });
    expect(params.is_active).toBeUndefined();
    expect(page.items[0]).toEqual({
      agentId: groupedAdvisor.agent_id,
      name: groupedAdvisor.name,
      groupId: groupedAdvisor.group_id,
      isActive: groupedAdvisor.is_active,
      activeLoad: groupedAdvisor.active_load,
    });
  });
});

describe('advisors.setGroup', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends group_id: null to clear the group, not an empty body', async () => {
    mockApiClient({
      [`PATCH /api/v1/advisors/${groupedAdvisor.agent_id}`]: { data: { ...groupedAdvisor, group_id: null } },
    });

    const advisor = await setGroup(groupedAdvisor.agent_id, null);

    expect(apiClient.patch).toHaveBeenCalledWith(`/api/v1/advisors/${groupedAdvisor.agent_id}`, { group_id: null });
    expect(advisor.groupId).toBeNull();
  });
});
