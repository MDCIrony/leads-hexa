import { apiClient, multipartConfig } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type IngestLeadRequest = components['schemas']['IngestLeadRequest'];
export type IntakeAcceptedResponse = components['schemas']['IntakeAcceptedResponse'];
export type IntakeRecord = components['schemas']['IntakeRecordResponse'];
export type LeadProcessedResponse = components['schemas']['LeadProcessedResponse'];

// Real paths are under /intake/leads and /intake/records, not /leads/ingest or /records —
// see schema.d.ts. Neither ingest nor batchUpload return a lead: the record still has to
// be processed asynchronously, which is what intakeJobs.waitForJob is for.
export async function ingest(body: IngestLeadRequest): Promise<IntakeAcceptedResponse> {
  const { data } = await apiClient.post<IntakeAcceptedResponse>('/api/v1/intake/leads/ingest', body);
  return data;
}

export async function batchUpload(file: File): Promise<IntakeAcceptedResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post<IntakeAcceptedResponse>(
    '/api/v1/intake/leads/batch-upload',
    formData,
    multipartConfig()
  );
  return data;
}

export interface ListRecordsFilters {
  status?: string;
  jobId?: string;
}

export async function listRecords(
  limit: number,
  offset: number,
  filters: ListRecordsFilters = {}
): Promise<PaginatedEnvelope<IntakeRecord>> {
  const { data } = await apiClient.get<components['schemas']['IntakeRecordsPageResponse']>('/api/v1/intake/records', {
    params: { limit, offset, status: filters.status, job_id: filters.jobId },
  });
  return data;
}

export async function promote(recordId: string, payload: Record<string, unknown>): Promise<LeadProcessedResponse> {
  const { data } = await apiClient.post<LeadProcessedResponse>(`/api/v1/intake/records/${recordId}/promote`, {
    payload,
  });
  return data;
}

export async function discard(recordId: string): Promise<void> {
  await apiClient.post(`/api/v1/intake/records/${recordId}/discard`);
}
