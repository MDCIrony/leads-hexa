import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import intakeAcceptedFixture from '../../test/fixtures/intake-accepted.json';
import { batchUpload, ingest } from './intake.service';

function fakeResponse<T>(data: T, status = 202) {
  return { data, status, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

describe('intake.ingest', () => {
  it('returns the 202 IntakeAcceptedResponse, not a lead', async () => {
    mockApiClient({ 'POST /api/v1/intake/leads/ingest': { status: 202, data: intakeAcceptedFixture } });

    const accepted = await ingest({
      first_name: 'Marta',
      last_name: 'Iglesias',
      company: 'Northwind',
      budget: 42000,
      industry: 'Technology',
    });

    expect(accepted.job_id).toBe(intakeAcceptedFixture.job_id);
    expect(accepted).not.toHaveProperty('lead_id');
  });
});

describe('intake.batchUpload', () => {
  it('sends multipart/form-data with the file under the `file` field', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(fakeResponse(intakeAcceptedFixture));

    const file = new File(['a,b\n1,2'], 'leads.csv', { type: 'text/csv' });
    await batchUpload(file);

    const [url, body, config] = postSpy.mock.calls[0];
    expect(url).toBe('/api/v1/intake/leads/batch-upload');
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get('file')).toBe(file);
    expect(config?.headers).toMatchObject({ 'Content-Type': 'multipart/form-data' });
  });
});
