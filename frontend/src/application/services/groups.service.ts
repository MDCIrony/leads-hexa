import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type Group = components['schemas']['SalesGroupResponse'];
export type GroupCreate = components['schemas']['SalesGroupCreate'];
export type GroupUpdate = components['schemas']['SalesGroupUpdate'];

export async function list(limit: number, offset: number): Promise<PaginatedEnvelope<Group>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedGroupsResponse']>('/api/v1/groups', {
    params: { limit, offset },
  });
  return data;
}

export async function create(body: GroupCreate): Promise<Group> {
  const { data } = await apiClient.post<Group>('/api/v1/groups', body);
  return data;
}

export async function update(id: string, body: GroupUpdate): Promise<Group> {
  const { data } = await apiClient.patch<Group>(`/api/v1/groups/${id}`, body);
  return data;
}

// No `get`: the API has no GET /groups/{id} — detail comes from the list, members from agents.list({groupId}).
export async function remove(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/groups/${id}`);
}
