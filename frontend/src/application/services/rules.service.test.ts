import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import scoringRulesPage from '../../test/fixtures/scoring-rules-page.json';
import assignmentRulesPage from '../../test/fixtures/assignment-rules-page.json';
import type { ApiErrorEnvelope } from '../../infrastructure/api/api-error';
import { assignment, scoring } from './rules.service';

describe('rules.scoring.list', () => {
  it('returns the paginated envelope intact', async () => {
    mockApiClient({ 'GET /api/v1/rules/scoring': { data: scoringRulesPage } });

    const page = await scoring.list(100, 0);

    expect(page.total).toBe(2);
  });
});

describe('rules.assignment.list', () => {
  it('returns the paginated envelope intact — pagination happens in memory server-side, transparently', async () => {
    mockApiClient({ 'GET /api/v1/rules/assignment': { data: assignmentRulesPage } });

    const page = await assignment.list(100, 0);

    expect(page.items[0].strategy).toBe('DIRECT_AGENT');
  });
});

describe('rules.assignment.create', () => {
  it('lets a 400 RULE_WITHOUT_TARGET bubble up distinguishable by error_code', async () => {
    const envelope: ApiErrorEnvelope = {
      error: true,
      error_code: 'RULE_WITHOUT_TARGET',
      message: 'An assignment rule needs a target group or target agents.',
    };
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new AxiosError('Bad Request', '400', undefined, undefined, {
        status: 400,
        statusText: 'Bad Request',
        headers: new AxiosHeaders(),
        config: { headers: new AxiosHeaders() },
        data: envelope,
      })
    );

    await expect(
      assignment.create({ name: 'Sin destino', min_score: 0, priority: 0, agent_match_mode: 'ANY' })
    ).rejects.toMatchObject({
      response: { data: { error_code: 'RULE_WITHOUT_TARGET' } },
    });
  });
});
