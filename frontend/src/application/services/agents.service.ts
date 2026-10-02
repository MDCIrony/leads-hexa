import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';
import type { AgentModel } from '../../domain/agent.model';
import { mapAgent, type AgentResponse } from '../mappers/agent.mapper';

// Omit until schema.d.ts is regenerated from identity: a group_id here is a 422 (ADR-0036).
export type AgentCreate = Omit<components['schemas']['AgentCreate'], 'group_id'>;
export type AgentUpdate = Omit<components['schemas']['AgentUpdate'], 'group_id'>;

/** No group filter: a group's members come from lead-core's GET /advisors?group_id= (ADR-0036). */
export interface ListAgentsFilters {
  /** Omitted entirely: the API only returns active agents when `is_active` is absent. */
  isActive?: boolean;
}

export async function list(
  limit: number,
  offset: number,
  filters: ListAgentsFilters = {}
): Promise<PaginatedEnvelope<AgentModel>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedAgentsResponse']>('/api/v1/agents', {
    params: { limit, offset, is_active: filters.isActive },
  });
  return { ...data, items: data.items.map(mapAgent) };
}

export async function get(id: string): Promise<AgentModel> {
  const { data } = await apiClient.get<AgentResponse>(`/api/v1/agents/${id}`);
  return mapAgent(data);
}

export async function create(body: AgentCreate): Promise<AgentModel> {
  const { data } = await apiClient.post<AgentResponse>('/api/v1/agents', body);
  return mapAgent(data);
}

export async function update(id: string, body: AgentUpdate): Promise<AgentModel> {
  const { data } = await apiClient.patch<AgentResponse>(`/api/v1/agents/${id}`, body);
  return mapAgent(data);
}

/** Deactivates, doesn't delete — DELETE returns 200 with the agent. Reactivate via update({isActive: true}). */
export async function deactivate(id: string): Promise<AgentModel> {
  const { data } = await apiClient.delete<AgentResponse>(`/api/v1/agents/${id}`);
  return mapAgent(data);
}
