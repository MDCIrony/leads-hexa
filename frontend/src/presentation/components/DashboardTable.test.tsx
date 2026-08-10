import { screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LeadStatus, type LeadModel } from '../../domain/lead.model';
import { DashboardTable } from './DashboardTable';

function buildLead(overrides: Partial<LeadModel>): LeadModel {
  return {
    id: 'lead-1',
    sourceId: 'source-1',
    firstName: 'Marta',
    lastName: 'Iglesias',
    email: 'marta@northwind.test',
    company: 'Northwind',
    budget: 42000,
    industry: 'Technology',
    customAttributes: {},
    phone: null,
    score: 40,
    status: LeadStatus.ASSIGNED,
    assignedAgentId: 'agent-1',
    createdAt: '2026-08-10T19:38:22.821565+00:00',
    ...overrides,
  };
}

describe('DashboardTable', () => {
  it('renders rows in the order it received them', () => {
    const leads = [buildLead({ id: 'a', firstName: 'Marta' }), buildLead({ id: 'b', firstName: 'Bruno' })];

    render(
      <MemoryRouter>
        <DashboardTable leads={leads} getDetailHref={(lead) => `/mis-leads/${lead.id}`} />
      </MemoryRouter>
    );

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Marta');
    expect(rows[2]).toHaveTextContent('Bruno');
  });

  it('links the detail action to whatever href the caller decides', () => {
    const leads = [buildLead({ id: 'lead-42' })];

    render(
      <MemoryRouter>
        <DashboardTable leads={leads} getDetailHref={(lead) => `/mis-leads/${lead.id}`} />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /ver detalle/i })).toHaveAttribute('href', '/mis-leads/lead-42');
  });

  it('offers no assign or discard action', () => {
    render(
      <MemoryRouter>
        <DashboardTable leads={[buildLead({})]} getDetailHref={() => '/mis-leads/lead-1'} />
      </MemoryRouter>
    );

    expect(screen.queryByRole('button', { name: /asignar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /descartar/i })).not.toBeInTheDocument();
  });
});
