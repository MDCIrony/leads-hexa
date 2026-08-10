import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type Tenant = components['schemas']['TenantResponse'];
export type TenantCreate = components['schemas']['TenantCreate'];
export type TenantUpdate = components['schemas']['TenantUpdate'];

export async function list(limit: number, offset: number): Promise<PaginatedEnvelope<Tenant>> {
  const { data } = await apiClient.get<components['schemas']['PaginatedTenantsResponse']>('/api/v1/tenants', {
    params: { limit, offset },
  });
  return data;
}

/** The manager goes nested under `manager`, not as a root-level `manager_email` field. */
export async function create(body: TenantCreate): Promise<Tenant> {
  const { data } = await apiClient.post<Tenant>('/api/v1/tenants', body);
  return data;
}

export async function update(id: string, body: TenantUpdate): Promise<Tenant> {
  const { data } = await apiClient.patch<Tenant>(`/api/v1/tenants/${id}`, body);
  return data;
}
