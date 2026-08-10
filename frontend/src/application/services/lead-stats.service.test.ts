import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import type { components } from '../../infrastructure/api/schema';
import { get } from './lead-stats.service';

// No captured fixture exists yet — typed literal against LeadStatsResponse.
const stats: components['schemas']['LeadStatsResponse'] = {
  total: 10,
  by_status: { NEW: 2, QUALIFIED: 3, DISQUALIFIED: 1, ASSIGNED: 3, FAILED: 1, PENDING: 0 },
  unassigned: 4,
  pending_intake: 2,
  load_by_agent: [{ agent_id: 'b51438ef-e4f1-4dc4-a6f1-c78db1cd0ba1', name: 'Fixture Agent', active_leads: 3 }],
};

describe('leadStats.get', () => {
  it('returns all five figures at once', async () => {
    mockApiClient({ 'GET /api/v1/leads/stats': { data: stats } });

    const result = await get();

    expect(result.total).toBe(10);
    expect(Object.keys(result.by_status)).toHaveLength(6);
    expect(result.load_by_agent[0].name).toBe('Fixture Agent');
  });
});
