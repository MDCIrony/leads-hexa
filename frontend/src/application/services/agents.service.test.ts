import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import { deactivate, list, update } from './agents.service';

function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

describe('agents.list', () => {
  it('omits is_active entirely when called with no filters — the API defaults to active-only', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(agentsPageFixture));

    await list(20, 0);

    // axios drops undefined query params at serialization time; asserting the
    // value (not key presence) matches what actually reaches the wire.
    const params = getSpy.mock.calls[0][1]?.params as Record<string, unknown> | undefined;
    expect(params?.is_active).toBeUndefined();
  });

  it('sends is_active=false when asked for deactivated agents', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(agentsPageFixture));

    await list(20, 0, { isActive: false });

    const params = getSpy.mock.calls[0][1]?.params as Record<string, unknown> | undefined;
    expect(params).toMatchObject({ is_active: false });
  });
});

describe('agents.update', () => {
  it('reactivates through PATCH {is_active: true}, not a dedicated endpoint', async () => {
    // mockApiClient only scripts get/post/put/delete (see src/test/mock-api.ts) — PATCH needs a direct spy.
    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue(fakeResponse(agentsPageFixture.items[0]));

    const agent = await update('b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1', { is_active: true });

    expect(patchSpy).toHaveBeenCalledWith('/api/v1/agents/b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1', { is_active: true });
    expect(agent.id).toBe('b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1');
  });
});

describe('agents.deactivate', () => {
  it('reads the 200 response as the agent, not a 204', async () => {
    mockApiClient({ 'DELETE /api/v1/agents/b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1': { data: agentsPageFixture.items[0] } });

    const agent = await deactivate('b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1');

    expect(agent.is_active).toBe(true);
  });
});
