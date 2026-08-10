import { AxiosHeaders } from 'axios';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import leadsPageFixture from '../../test/fixtures/leads-page.json';
import { MyLeadsPage } from './MyLeadsPage';

function fakeResponse<T>(data: T) {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

// Two items so an order assertion actually means something.
const secondLead = { ...leadsPageFixture.items[0], id: 'a-second-lead', first_name: 'Bruno' };
const twoLeadsPage = { ...leadsPageFixture, items: [leadsPageFixture.items[0], secondLead], total: 2 };

describe('MyLeadsPage', () => {
  it('renders leads/mine in the order the API returns, unsorted', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(twoLeadsPage));

    renderWithProviders(<MyLeadsPage />, { role: 'AGENT' });

    const rows = await screen.findAllByRole('row');
    // Row 0 is the header.
    expect(rows[1]).toHaveTextContent('Marta');
    expect(rows[2]).toHaveTextContent('Bruno');
  });

  it('sends the typed search as `q` and the picked status as `status`', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(leadsPageFixture));
    const user = userEvent.setup();

    renderWithProviders(<MyLeadsPage />, { role: 'AGENT' });
    await screen.findAllByRole('row');

    await user.type(screen.getByLabelText('Buscar leads'), 'northwind');
    await waitFor(() => {
      const lastCall = getSpy.mock.calls.at(-1);
      expect(lastCall?.[1]?.params).toMatchObject({ q: 'northwind' });
    });

    await user.selectOptions(screen.getByLabelText('Filtrar por estado'), 'ASSIGNED');
    await waitFor(() => {
      const lastCall = getSpy.mock.calls.at(-1);
      expect(lastCall?.[1]?.params).toMatchObject({ status: 'ASSIGNED' });
    });

    expect(getSpy.mock.calls.every((call) => call[0] === '/api/v1/leads/mine')).toBe(true);
  });

  it('offers no assign or discard action', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(fakeResponse(leadsPageFixture));

    renderWithProviders(<MyLeadsPage />, { role: 'AGENT' });
    await screen.findAllByRole('row');

    expect(screen.queryByRole('button', { name: /asignar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /descartar/i })).not.toBeInTheDocument();
  });

  it('shows an empty state instead of a blank screen when the agent has nothing assigned', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(
      fakeResponse({ items: [], total: 0, limit: 20, offset: 0, has_more: false })
    );

    renderWithProviders(<MyLeadsPage />, { role: 'AGENT' });

    expect(await screen.findByText('No tienes leads asignados todavía.')).toBeInTheDocument();
  });
});
