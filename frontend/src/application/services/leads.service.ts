import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type Lead = components['schemas']['LeadResponse'];
export type LeadDetail = components['schemas']['LeadDetailResponse'];

export interface ListLeadsFilters {
  status?: string;
  assignedAgentId?: string;
  groupId?: string;
  sourceId?: string;
  /** Sent to the API as `q`; the backend matches it literally, escaping `%` and `_` itself. */
  search?: string;
}

export async function list(
  limit: number,
  offset: number,
  filters: ListLeadsFilters = {}
): Promise<PaginatedEnvelope<Lead>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedLeadsResponse']>('/api/v1/leads', {
    params: {
      limit,
      offset,
      status: filters.status,
      assigned_agent_id: filters.assignedAgentId,
      group_id: filters.groupId,
      source_id: filters.sourceId,
      q: filters.search,
    },
  });
  return data;
}

export interface ListMyLeadsFilters {
  status?: string;
  search?: string;
}

/** The caller is always the agent themselves here, so there's no agent/group filter to offer. */
export async function listMine(
  limit: number,
  offset: number,
  filters: ListMyLeadsFilters = {}
): Promise<PaginatedEnvelope<Lead>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedLeadsResponse']>('/api/v1/leads/mine', {
    params: { limit, offset, status: filters.status, q: filters.search },
  });
  return data;
}

export async function get(id: string): Promise<LeadDetail> {
  const { data } = await apiClient.get<LeadDetail>(`/api/v1/leads/${id}`);
  return data;
}

export async function assign(id: string, agentId: string): Promise<LeadDetail> {
  const { data } = await apiClient.post<LeadDetail>(`/api/v1/leads/${id}/assign`, { agent_id: agentId });
  return data;
}

export async function discard(id: string, reason = ''): Promise<LeadDetail> {
  const { data } = await apiClient.post<LeadDetail>(`/api/v1/leads/${id}/discard`, { reason });
  return data;
}
