import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';
import type { AdvisorModel } from '../../domain/advisor.model';
import { mapAdvisor, type AdvisorResponse } from '../mappers/advisor.mapper';

export interface ListAdvisorsFilters {
  groupId?: string;
  /** Omitted: unlike /agents, /advisors then returns active and inactive alike. */
  isActive?: boolean;
}

export async function list(
  limit: number,
  offset: number,
  filters: ListAdvisorsFilters = {}
): Promise<PaginatedEnvelope<AdvisorModel>> {
  const { data } = await apiClient.get<components['schemas']['AdvisorsPageResponse']>('/api/v1/advisors', {
    params: { limit, offset, group_id: filters.groupId, is_active: filters.isActive },
  });
  return { ...data, items: data.items.map(mapAdvisor) };
}

/** `null` clears the group: the field is required precisely so that null can mean that. */
export async function setGroup(agentId: string, groupId: string | null): Promise<AdvisorModel> {
  const body: components['schemas']['AdvisorGroupUpdate'] = { group_id: groupId };
  const { data } = await apiClient.patch<AdvisorResponse>(`/api/v1/advisors/${agentId}`, body);
  return mapAdvisor(data);
}
