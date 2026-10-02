import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import stats from '../../test/fixtures/intake-stats.json';
import { get } from './intake-stats.service';

describe('intakeStats.get', () => {
  it('returns the pending, rejected and pending_intake figures', async () => {
    mockApiClient({ 'GET /api/v1/intake/stats': { data: stats } });

    const result = await get();

    expect(result).toEqual(stats);
  });
});
