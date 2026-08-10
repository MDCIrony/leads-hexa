import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import intakeJobCompleted from '../../test/fixtures/intake-job-completed.json';
import { waitForJob } from './intake-jobs.service';

function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

function job(overrides: Partial<typeof intakeJobCompleted>) {
  return { ...intakeJobCompleted, ...overrides };
}

describe('intakeJobs.waitForJob', () => {
  it('stops as soon as the job reaches COMPLETED', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(job({ status: 'COMPLETED' })));

    const result = await waitForJob(intakeJobCompleted.id, { intervalMs: 0 });

    expect(result.status).toBe('COMPLETED');
    expect(getSpy).toHaveBeenCalledTimes(1);
  });

  it('stops as soon as the job reaches FAILED', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(job({ status: 'FAILED' })));

    const result = await waitForJob(intakeJobCompleted.id, { intervalMs: 0 });

    expect(result.status).toBe('FAILED');
  });

  it('gives up at the attempt cap instead of polling forever', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(job({ status: 'PROCESSING' })));

    const result = await waitForJob(intakeJobCompleted.id, { maxAttempts: 3, intervalMs: 0 });

    expect(result.status).toBe('PROCESSING');
    // One initial read plus up to maxAttempts retries.
    expect(getSpy).toHaveBeenCalledTimes(4);
  });

  it('returns a COMPLETED job with failures instead of throwing — terminated is not the same as succeeded', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(job({ status: 'COMPLETED', failed: 10 })));

    const result = await waitForJob(intakeJobCompleted.id, { intervalMs: 0 });

    expect(result.status).toBe('COMPLETED');
    expect(result.failed).toBe(10);
  });
});
