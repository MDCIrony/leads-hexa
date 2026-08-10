import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';
import type { LeadModel } from '../../domain/lead.model';
import { mapLead, mapLeadDetail } from '../mappers/lead.mapper';

type LeadDetailResponse = components['schemas']['LeadDetailResponse'];

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
): Promise<PaginatedEnvelope<LeadModel>> {
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
  return { ...data, items: data.items.map(mapLead) };
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
): Promise<PaginatedEnvelope<LeadModel>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedLeadsResponse']>('/api/v1/leads/mine', {
    params: { limit, offset, status: filters.status, q: filters.search },
  });
  return { ...data, items: data.items.map(mapLead) };
}

export async function get(id: string): Promise<LeadModel> {
  const { data } = await apiClient.get<LeadDetailResponse>(`/api/v1/leads/${id}`);
  return mapLeadDetail(data);
}

export async function assign(id: string, agentId: string): Promise<LeadModel> {
  const { data } = await apiClient.post<LeadDetailResponse>(`/api/v1/leads/${id}/assign`, { agent_id: agentId });
  return mapLeadDetail(data);
}

export async function discard(id: string, reason = ''): Promise<LeadModel> {
  const { data } = await apiClient.post<LeadDetailResponse>(`/api/v1/leads/${id}/discard`, { reason });
  return mapLeadDetail(data);
}
