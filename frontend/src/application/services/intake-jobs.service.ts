import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/intake-schema';
import type { PaginatedEnvelope } from '../data/use-paginated';

export type IntakeJob = components['schemas']['IntakeJobResponse'];

// COMPLETED only means the job finished, not that every row succeeded — a job can be
// COMPLETED with failed > 0. "Terminated" and "succeeded" are different questions,
// answered by `succeeded`/`failed`, not by the status alone.
const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED']);

export interface ListJobsFilters {
  status?: string;
}

export async function list(
  limit: number,
  offset: number,
  filters: ListJobsFilters = {}
): Promise<PaginatedEnvelope<IntakeJob>> {
  const { data } = await apiClient.get<components['schemas']['IntakeJobsPageResponse']>('/api/v1/intake/jobs', {
    params: { limit, offset, status: filters.status },
  });
  return data;
}

export async function get(id: string): Promise<IntakeJob> {
  const { data } = await apiClient.get<IntakeJob>(`/api/v1/intake/jobs/${id}`);
  return data;
}

export async function reprocess(id: string): Promise<IntakeJob> {
  const { data } = await apiClient.post<IntakeJob>(`/api/v1/intake/jobs/${id}/reprocess`);
  return data;
}

export interface WaitForJobOptions {
  maxAttempts?: number;
  intervalMs?: number;
}

/**
 * Polls GET /intake/jobs/{id} until it reaches COMPLETED/FAILED, mirroring
 * bruno/flows/lead-processing/Await lead processing.bru (25 attempts, 200ms apart).
 * A job still short of terminal when attempts run out is returned as-is instead of
 * thrown or retried forever — a fixed sleep would hang the tab the day the backend
 * is slow, and the caller is the one who knows whether to keep waiting or bail.
 */
export async function waitForJob(
  jobId: string,
  { maxAttempts = 25, intervalMs = 200 }: WaitForJobOptions = {}
): Promise<IntakeJob> {
  let job = await get(jobId);
  let attempts = 0;
  while (!TERMINAL_STATUSES.has(job.status) && attempts < maxAttempts) {
    attempts += 1;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    job = await get(jobId);
  }
  // Returning a non-terminal job as if it were the answer is what let a screen
  // read `succeeded` off a job still PENDING and report "0 rows loaded" as a
  // success. The caller has to be able to tell the two apart.
  return job;
}

/** True when waitForJob gave up rather than the job reaching a terminal state. */
export function stillRunning(job: IntakeJob): boolean {
  return !TERMINAL_STATUSES.has(job.status);
}
