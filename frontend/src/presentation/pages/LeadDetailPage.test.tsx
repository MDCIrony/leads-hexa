import { AxiosHeaders } from 'axios';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import leadDetailFixture from '../../test/fixtures/lead-detail.json';
import error404 from '../../test/fixtures/error-404.json';
import { LeadDetailPage } from './LeadDetailPage';

// LeadDetailPage reads :leadId via useParams, so it needs an actual matched
// route in the test tree, not just a MemoryRouter with an initial entry.
const routedPage = (
  <Routes>
    <Route path="/mis-leads/:leadId" element={<LeadDetailPage />} />
  </Routes>
);

function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

function fakeAxiosError(status: number, data: unknown) {
  const error = new Error('request failed') as Error & { isAxiosError: true; response: unknown };
  error.isAxiosError = true;
  error.response = { status, data, statusText: '', headers: new AxiosHeaders(), config: {} };
  return error;
}

describe('LeadDetailPage', () => {
  it('shows the score breakdown rule by rule, not just the total', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(leadDetailFixture));

    renderWithProviders(routedPage, { role: 'AGENT', route: `/mis-leads/${leadDetailFixture.id}` });

    expect(await screen.findByText(`${leadDetailFixture.score} pts`)).toBeInTheDocument();
    for (const rule of leadDetailFixture.score_breakdown) {
      expect(screen.getByText(rule.name)).toBeInTheDocument();
      expect(screen.getByText(`+${rule.score_delta}`)).toBeInTheDocument();
    }
  });

  it('treats a colleague\'s lead as nonexistent instead of forbidden', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValue(fakeAxiosError(error404.status, error404.data));

    renderWithProviders(routedPage, { role: 'AGENT', route: '/mis-leads/someone-elses-lead' });

    expect(await screen.findByText('No existe.')).toBeInTheDocument();
    expect(screen.queryByText(/no tienes acceso/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/otro asesor/i)).not.toBeInTheDocument();
  });

  it('offers no assign or discard action', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(leadDetailFixture));

    renderWithProviders(routedPage, { role: 'AGENT', route: `/mis-leads/${leadDetailFixture.id}` });
    await screen.findByText(`${leadDetailFixture.score} pts`);

    expect(screen.queryByRole('button', { name: /asignar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /descartar/i })).not.toBeInTheDocument();
  });
});
