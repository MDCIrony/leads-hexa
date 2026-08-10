import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import intakeAcceptedFixture from '../../test/fixtures/intake-accepted.json';
import intakeJobCompletedFixture from '../../test/fixtures/intake-job-completed.json';
import { BulkUploadPage } from './BulkUploadPage';

function fakeResponse<T>(data: T, status = 202) {
  return { data, status, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

async function selectFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, file);
}

describe('BulkUploadPage', () => {
  it('uploads the real file as multipart/form-data', async () => {
    const batchAccepted = { ...intakeAcceptedFixture, record_ids: [] };
    mockApiClient({ [`GET /api/v1/intake/jobs/${intakeJobCompletedFixture.id}`]: { data: intakeJobCompletedFixture } });
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue(fakeResponse(batchAccepted));
    renderWithProviders(<BulkUploadPage />, { role: 'MANAGER' });

    const file = new File(['first_name,last_name\nMarta,Iglesias'], 'leads-mixed.csv', { type: 'text/csv' });
    await selectFile(file);
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar Carga' }));

    await screen.findByText(/cargada/);
    const [url, body, config] = postSpy.mock.calls[0];
    expect(url).toBe('/api/v1/intake/leads/batch-upload');
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get('file')).toBe(file);
    expect(config?.headers).toMatchObject({ 'Content-Type': 'multipart/form-data' });
  });

  it('shows both counters for a job completed with failures, not a plain success', async () => {
    const batchAccepted = { ...intakeAcceptedFixture, record_ids: [] };
    const mixedJob = { ...intakeJobCompletedFixture, total_items: 2, succeeded: 1, failed: 1 };
    mockApiClient({ [`GET /api/v1/intake/jobs/${intakeJobCompletedFixture.id}`]: { data: mixedJob } });
    vi.spyOn(apiClient, 'post').mockResolvedValue(fakeResponse(batchAccepted));
    renderWithProviders(<BulkUploadPage />, { role: 'MANAGER' });

    const file = new File(['a,b'], 'leads-mixed.csv', { type: 'text/csv' });
    await selectFile(file);
    await userEvent.click(screen.getByRole('button', { name: 'Iniciar Carga' }));

    expect(await screen.findByText('1 fila cargada, 1 rechazada.')).toBeInTheDocument();
  });
});
