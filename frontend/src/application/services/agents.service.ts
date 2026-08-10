import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type Agent = components['schemas']['AgentResponse'];
export type AgentCreate = components['schemas']['AgentCreate'];
export type AgentUpdate = components['schemas']['AgentUpdate'];

export interface ListAgentsFilters {
  groupId?: string;
  /** Omitted entirely: the API only returns active agents when `is_active` is absent. */
  isActive?: boolean;
}

export async function list(
  limit: number,
  offset: number,
  filters: ListAgentsFilters = {}
): Promise<PaginatedEnvelope<Agent>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedAgentsResponse']>('/api/v1/agents', {
    params: { limit, offset, group_id: filters.groupId, is_active: filters.isActive },
  });
  return data;
}

export async function get(id: string): Promise<Agent> {
  const { data } = await apiClient.get<Agent>(`/api/v1/agents/${id}`);
  return data;
}

export async function create(body: AgentCreate): Promise<Agent> {
  const { data } = await apiClient.post<Agent>('/api/v1/agents', body);
  return data;
}

export async function update(id: string, body: AgentUpdate): Promise<Agent> {
  const { data } = await apiClient.patch<Agent>(`/api/v1/agents/${id}`, body);
  return data;
}

/** Deactivates, doesn't delete — DELETE returns 200 with the agent. Reactivate via update({isActive: true}). */
export async function deactivate(id: string): Promise<Agent> {
  const { data } = await apiClient.delete<Agent>(`/api/v1/agents/${id}`);
  return data;
}
