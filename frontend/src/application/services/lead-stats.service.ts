import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';

export type LeadStats = components['schemas']['LeadStatsResponse'];

/** `by_status` always carries all six statuses; a `from` after `to` responds 400 INVALID_DATE_RANGE. */
export async function get(from?: string, to?: string): Promise<LeadStats> {
  const { data } = await apiClient.get<LeadStats>('/api/v1/leads/stats', { params: { from, to } });
  return data;
}
