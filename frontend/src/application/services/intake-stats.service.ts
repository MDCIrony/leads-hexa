import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/intake-schema';

export type IntakeStats = components['schemas']['IntakeStatsResponse'];

/**
 * Lives apart from lead-stats: the figure belongs to the intake service, so a dashboard reads
 * both and must let one fail without the other. Manager only; `pending_intake` is the figure
 * `GET /leads/stats` used to carry.
 */
export async function get(): Promise<IntakeStats> {
  const { data } = await apiClient.get<IntakeStats>('/api/v1/intake/stats');
  return data;
}
