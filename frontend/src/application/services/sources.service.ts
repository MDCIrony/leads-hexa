import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type Source = components['schemas']['LeadSourceResponse'];
export type SourceCreate = components['schemas']['LeadSourceCreate'];
export type SourceUpdate = components['schemas']['LeadSourceUpdate'];

export async function list(limit: number, offset: number): Promise<PaginatedEnvelope<Source>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedSourcesResponse']>('/api/v1/sources', {
    params: { limit, offset },
  });
  return data;
}

export async function create(body: SourceCreate): Promise<Source> {
  const { data } = await apiClient.post<Source>('/api/v1/sources', body);
  return data;
}

export async function update(id: string, body: SourceUpdate): Promise<Source> {
  const { data } = await apiClient.patch<Source>(`/api/v1/sources/${id}`, body);
  return data;
}

export async function remove(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/sources/${id}`);
}
