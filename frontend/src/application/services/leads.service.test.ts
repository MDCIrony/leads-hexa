import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import leadsPageFixture from '../../test/fixtures/leads-page.json';
import leadDetailFixture from '../../test/fixtures/lead-detail.json';
import { assign, discard, get, list, listMine } from './leads.service';

function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

describe('leads.list', () => {
  it('translates `search` to `q`', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(leadsPageFixture));

    await list(20, 0, { search: '50%' });

    const params = getSpy.mock.calls[0][1]?.params as Record<string, unknown> | undefined;
    expect(params?.q).toBe('50%');
    // The backend escapes % and _ itself; the service must not touch the string.
    expect(params?.search).toBeUndefined();
  });

  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/leads': { data: leadsPageFixture } });

    const page = await list(20, 0);

    expect(page.total).toBe(1);
    expect(page.has_more).toBe(false);
  });
});

describe('leads.listMine', () => {
  it('has no assigned_agent_id or group_id filter to offer', async () => {
    mockApiClient({ 'GET /api/v1/leads/mine': { data: leadsPageFixture } });

    // @ts-expect-error listMine's caller is always the requesting agent — no agent/group filter exists.
    await listMine(20, 0, { assignedAgentId: 'x' });
  });
});

describe('leads.get, leads.assign, leads.discard', () => {
  it('reads a single lead', async () => {
    mockApiClient({ [`GET /api/v1/leads/${leadDetailFixture.id}`]: { data: leadDetailFixture } });

    const lead = await get(leadDetailFixture.id);

    expect(lead.id).toBe(leadDetailFixture.id);
  });

  it('assigns to an agent id', async () => {
    mockApiClient({
      [`POST /api/v1/leads/${leadDetailFixture.id}/assign`]: { data: leadDetailFixture },
    });

    const lead = await assign(leadDetailFixture.id, leadDetailFixture.assigned_agent_id as string);

    expect(lead.assignedAgentId).toBe(leadDetailFixture.assigned_agent_id);
  });

  it('discards with a reason', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(fakeResponse(leadDetailFixture));

    await discard(leadDetailFixture.id, 'duplicate');

    expect(postSpy).toHaveBeenCalledWith(`/api/v1/leads/${leadDetailFixture.id}/discard`, {
      reason: 'duplicate',
    });
  });
});
