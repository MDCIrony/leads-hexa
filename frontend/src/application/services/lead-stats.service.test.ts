import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import stats from '../../test/fixtures/lead-stats.json';
import { get } from './lead-stats.service';

describe('leadStats.get', () => {
  it('returns all five figures at once', async () => {
    mockApiClient({ 'GET /api/v1/leads/stats': { data: stats } });

    const result = await get();

    expect(result.total).toBe(stats.total);
    expect(Object.keys(result.by_status)).toHaveLength(6);
    expect(result.load_by_agent[0].name).toBe(stats.load_by_agent[0].name);
  });
});
