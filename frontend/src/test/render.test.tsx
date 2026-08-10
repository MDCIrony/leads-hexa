import { useEffect, useState } from 'react';
import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { apiClient } from '../infrastructure/api/api-client';
import type { components } from '../infrastructure/api/schema';
import { useSession } from '../application/session/use-session';
import leadsPage from './fixtures/leads-page.json';
import { mockApiClient } from './mock-api';
import { renderWithProviders } from './render';

type PaginatedLeads = components['schemas']['PaginatedLeadsResponse'];

// Stand-in for what a real list view does: read the session, call its
// service, render the result. Proves renderWithProviders + mockApiClient
// wire together, not any one view's markup.
function DemoView() {
  const { user } = useSession();
  const [leads, setLeads] = useState<PaginatedLeads | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedLeads>('/api/v1/leads').then(({ data }) => setLeads(data));
  }, []);

  if (!leads) return <p>Cargando...</p>;
  return (
    <p>
      {user?.name} ve {leads.total} leads
    </p>
  );
}

describe('renderWithProviders + mockApiClient', () => {
  it('renders a view against a role-scoped session and a captured fixture', async () => {
    mockApiClient({
      'GET /api/v1/leads': { data: leadsPage as PaginatedLeads },
    });

    renderWithProviders(<DemoView />, { role: 'MANAGER' });

    await waitFor(() => expect(screen.getByText(/ve \d+ leads/)).toBeInTheDocument());
  });
});
