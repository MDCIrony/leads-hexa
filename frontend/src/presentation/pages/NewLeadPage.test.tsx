import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import type { components } from '../../infrastructure/api/schema';
import intakeAcceptedFixture from '../../test/fixtures/intake-accepted.json';
import intakeJobCompletedFixture from '../../test/fixtures/intake-job-completed.json';
import leadDetailFixture from '../../test/fixtures/lead-detail.json';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import { NewLeadPage } from './NewLeadPage';

type RecordsPage = components['schemas']['IntakeRecordsPageResponse'];

// No captured fixture exists for GET /intake/records — the sixteen captured
// pages don't cover this envelope. Built by hand, typed against the
// generated schema so a contract change still breaks compilation.
function recordsPage(overrides: Partial<RecordsPage['items'][number]> = {}): RecordsPage {
  return {
    items: [
      {
        id: intakeAcceptedFixture.record_ids[0],
        source_id: intakeJobCompletedFixture.source_id,
        status: 'PROMOTED',
        payload: { company: 'Northwind' },
        errors: [],
        received_at: intakeJobCompletedFixture.created_at,
        processed_at: intakeJobCompletedFixture.completed_at,
        lead_id: leadDetailFixture.id,
        ...overrides,
      },
    ],
    total: 1,
    limit: 1,
    offset: 0,
    has_more: false,
  };
}

async function fillRequiredFields() {
  await userEvent.type(screen.getByLabelText('Nombre'), 'Marta');
  await userEvent.type(screen.getByLabelText('Apellidos'), 'Iglesias');
  await userEvent.type(screen.getByLabelText('Empresa'), 'Northwind');
  await userEvent.type(screen.getByLabelText('Sector'), 'Technology');
}

describe('NewLeadPage validation', () => {
  it('does not submit when a required field is missing', async () => {
    const postSpy = vi.spyOn(apiClient, 'post');
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));

    expect(await screen.findAllByText('Obligatorio.')).not.toHaveLength(0);
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('does not submit when the budget is not a number', async () => {
    const postSpy = vi.spyOn(apiClient, 'post');
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await fillRequiredFields();
    await userEvent.type(screen.getByLabelText('Presupuesto'), 'mucho');
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));

    expect(await screen.findByText('Tiene que ser un número.')).toBeInTheDocument();
    expect(postSpy).not.toHaveBeenCalled();
  });
});

describe('NewLeadPage outcomes', () => {
  it('waits for the terminal job state before declaring an outcome', async () => {
    mockApiClient({
      'POST /api/v1/intake/leads/ingest': { status: 202, data: intakeAcceptedFixture },
      'GET /api/v1/intake/jobs/de88f66a-ff78-4630-bf2a-e1afcc6f387e': { data: intakeJobCompletedFixture },
      'GET /api/v1/intake/records': { data: recordsPage() },
      'GET /api/v1/leads/02447540-bc70-4f39-9a2b-42c2c4adf7b7': { data: leadDetailFixture },
      'GET /api/v1/agents/cdc44a50-543b-4bf1-91f6-1abbaf16a94f': { data: agentsPageFixture.items[0] },
    });
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await fillRequiredFields();
    await userEvent.type(screen.getByLabelText('Presupuesto'), '42000');
    // Only submitted, not clicked-and-awaited: the assertion has to observe the
    // in-flight state before the mocked chain (ingest → poll → record → lead →
    // agent) settles, which userEvent.click's own act() flush would otherwise race.
    const submit = userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));
    expect(screen.queryByText(/Asignado a/)).not.toBeInTheDocument();
    await submit;

    expect(await screen.findByText(/Asignado a/)).toBeInTheDocument();
    expect(screen.getByText(agentsPageFixture.items[0].name)).toBeInTheDocument();
  });

  it('shows an unassigned lead as unassigned, not as success', async () => {
    const unassignedLead = { ...leadDetailFixture, status: 'UNASSIGNED', assigned_agent_id: null, assigned_at: null };
    mockApiClient({
      'POST /api/v1/intake/leads/ingest': { status: 202, data: intakeAcceptedFixture },
      'GET /api/v1/intake/jobs/de88f66a-ff78-4630-bf2a-e1afcc6f387e': { data: intakeJobCompletedFixture },
      'GET /api/v1/intake/records': { data: recordsPage() },
      'GET /api/v1/leads/02447540-bc70-4f39-9a2b-42c2c4adf7b7': { data: unassignedLead },
    });
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await fillRequiredFields();
    await userEvent.type(screen.getByLabelText('Presupuesto'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));

    expect(await screen.findByText(/Ninguna regla de asignación lo recogió/)).toBeInTheDocument();
  });

  it('shows the disqualification reason for a disqualified lead', async () => {
    const disqualifiedLead = {
      ...leadDetailFixture,
      status: 'DISQUALIFIED',
      assigned_agent_id: null,
      assigned_at: null,
      disqualification_reason: 'Sin vía de contacto',
    };
    mockApiClient({
      'POST /api/v1/intake/leads/ingest': { status: 202, data: intakeAcceptedFixture },
      'GET /api/v1/intake/jobs/de88f66a-ff78-4630-bf2a-e1afcc6f387e': { data: intakeJobCompletedFixture },
      'GET /api/v1/intake/records': { data: recordsPage() },
      'GET /api/v1/leads/02447540-bc70-4f39-9a2b-42c2c4adf7b7': { data: disqualifiedLead },
    });
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await fillRequiredFields();
    await userEvent.type(screen.getByLabelText('Presupuesto'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));

    expect(await screen.findByText(/Sin vía de contacto/)).toBeInTheDocument();
  });

  it('shows the per-field reason for a rejected record', async () => {
    mockApiClient({
      'POST /api/v1/intake/leads/ingest': { status: 202, data: intakeAcceptedFixture },
      'GET /api/v1/intake/jobs/de88f66a-ff78-4630-bf2a-e1afcc6f387e': { data: intakeJobCompletedFixture },
      'GET /api/v1/intake/records': {
        data: recordsPage({
          status: 'REJECTED',
          lead_id: null,
          errors: [{ field: 'email', message: 'Formato de correo inválido.', received_value: 'bruno@@salas' }],
        }),
      },
    });
    renderWithProviders(<NewLeadPage />, { role: 'MANAGER' });

    await fillRequiredFields();
    await userEvent.type(screen.getByLabelText('Presupuesto'), '1000');
    await userEvent.click(screen.getByRole('button', { name: 'Dar de alta' }));

    expect(await screen.findByText('Formato de correo inválido.')).toBeInTheDocument();
  });
});
