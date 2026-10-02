import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosHeaders, type AxiosResponse } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import advisorsPageFixture from '../../test/fixtures/advisors-page.json';
import groupsPageFixture from '../../test/fixtures/groups-page.json';
import { AgentsPage } from './AgentsPage';
import { AppRoutes } from '../routes/app-routes';

const [activeAgent, signedInManager] = agentsPageFixture.items;
// Derived from the advisor, not from items[1]: that one is the signed-in
// manager, whom the page filters out of its own list.
const inactiveAgent = {
  ...activeAgent,
  id: '2f0d6f4e-6a1b-4a0c-9d4d-0b6f2c1a8e77',
  name: 'Fixture Agent Inactivo',
  is_active: false,
};
const mixedFixture = { ...agentsPageFixture, items: [activeAgent, inactiveAgent, signedInManager] };
const [fixtureGroup] = groupsPageFixture.items;
const newAgent = { ...activeAgent, id: '7c1e2b8a-3f4d-4e5a-9b6c-1d2e3f4a5b6c', name: 'Nuevo Asesor', email: 'nuevo@fixtures.test' };
const newAdvisor = { agent_id: newAgent.id, name: newAgent.name, group_id: fixtureGroup.id, is_active: true, active_load: 0 };

function fakeResponse<T>(data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

function mockAgents(overrides: Record<string, unknown> = {}) {
  mockApiClient({
    'GET /api/v1/agents': { data: mixedFixture },
    // The inactive agent is left out on purpose: lead-core's projection may lag behind identity.
    'GET /api/v1/advisors': { data: advisorsPageFixture },
    'GET /api/v1/groups': { data: groupsPageFixture },
    ...overrides,
  });
}

async function fillNewAgent() {
  await userEvent.type(screen.getByLabelText('Nombre completo'), newAgent.name);
  await userEvent.type(screen.getByLabelText('Correo'), newAgent.email);
  await userEvent.type(screen.getByLabelText('Contraseña'), 'Secret123');
}

describe('AgentsPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('deactivates through DELETE, with a warning instead of the word "eliminar"', async () => {
    mockAgents();
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    const deactivateButton = await screen.findByRole('button', { name: 'Desactivar' });
    expect(screen.queryByRole('button', { name: /eliminar/i })).not.toBeInTheDocument();
    expect(deactivateButton).toHaveAttribute('title', expect.stringContaining('deja de poder entrar'));

    const deleteSpy = vi
      .spyOn(apiClient, 'delete')
      .mockResolvedValue(fakeResponse({ ...activeAgent, is_active: false }));
    await userEvent.click(deactivateButton);

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(`/api/v1/agents/${activeAgent.id}`));
  });

  it('reactivates through PATCH {is_active: true}', async () => {
    mockAgents();
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    const reactivateButton = await screen.findByRole('button', { name: 'Reactivar' });

    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue(fakeResponse({ ...inactiveAgent, is_active: true }));
    await userEvent.click(reactivateButton);

    await waitFor(() =>
      expect(patchSpy).toHaveBeenCalledWith(`/api/v1/agents/${inactiveAgent.id}`, { is_active: true })
    );
  });

  it('shows EMAIL_ALREADY_EXISTS as the message from a duplicate signup', async () => {
    mockAgents({
      'POST /api/v1/agents': {
        status: 400,
        error: { error: true, error_code: 'EMAIL_ALREADY_EXISTS', message: 'El correo ya está registrado.' },
      },
    });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    await screen.findByText(activeAgent.name);
    await userEvent.type(screen.getByLabelText('Nombre completo'), 'Nuevo Asesor');
    await userEvent.type(screen.getByLabelText('Correo'), activeAgent.email);
    await userEvent.type(screen.getByLabelText('Contraseña'), 'Secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar asesor' }));

    expect(await screen.findByText('El correo ya está registrado.')).toBeInTheDocument();
  });

  it('leaves the signed-in manager out of the list they administer', async () => {
    mockAgents();
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    await screen.findByText(activeAgent.name);
    expect(screen.queryByText(signedInManager.name)).not.toBeInTheDocument();
  });

  it('shows the group and load from /advisors, and no group for an agent it has not projected yet', async () => {
    mockAgents();
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    const groupSelect = await screen.findByRole('combobox', { name: `Grupo de ${activeAgent.name}` });
    expect(groupSelect).toHaveValue(fixtureGroup.id);
    expect(screen.getByText(/1 leads activos/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: `Grupo de ${inactiveAgent.name}` })).toHaveValue('');
  });

  it('creates the agent without group_id, then sets the group through PATCH /advisors', async () => {
    mockAgents({
      'POST /api/v1/agents': { status: 201, data: newAgent },
      [`PATCH /api/v1/advisors/${newAgent.id}`]: { data: newAdvisor },
    });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    await screen.findByText(activeAgent.name);
    await fillNewAgent();
    await userEvent.selectOptions(screen.getByLabelText('Grupo'), fixtureGroup.id);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar asesor' }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(`/api/v1/advisors/${newAgent.id}`, { group_id: fixtureGroup.id })
    );
    const [, createBody] = vi.mocked(apiClient.post).mock.calls[0];
    expect(createBody).not.toHaveProperty('group_id');
  });

  it('skips /advisors when no group was chosen', async () => {
    mockAgents({ 'POST /api/v1/agents': { status: 201, data: newAgent } });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    await screen.findByText(activeAgent.name);
    await fillNewAgent();
    await userEvent.click(screen.getByRole('button', { name: 'Guardar asesor' }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(apiClient.patch).not.toHaveBeenCalled();
  });

  it('keeps the agent listed and says so when the group step fails after creating it', async () => {
    mockAgents({
      'GET /api/v1/agents': { responses: [{ data: mixedFixture }, { data: { ...mixedFixture, items: [...mixedFixture.items, newAgent] } }] },
      'POST /api/v1/agents': { status: 201, data: newAgent },
      [`PATCH /api/v1/advisors/${newAgent.id}`]: {
        status: 404,
        error: { error: true, error_code: 'GROUP_NOT_FOUND', message: 'El grupo no existe.' },
      },
    });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    await screen.findByText(activeAgent.name);
    await fillNewAgent();
    await userEvent.selectOptions(screen.getByLabelText('Grupo'), fixtureGroup.id);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar asesor' }));

    expect(await screen.findByRole('heading', { name: newAgent.name })).toBeInTheDocument();
    // Read after the refetch: reloading the list must not take the form, and its message, with it.
    expect(screen.getByText(`${newAgent.name} se registró sin grupo: El grupo no existe.`)).toBeInTheDocument();
    expect(apiClient.delete).not.toHaveBeenCalled();
  });

  it('clears a group through PATCH /advisors {group_id: null}', async () => {
    mockAgents({
      [`PATCH /api/v1/advisors/${activeAgent.id}`]: { data: { ...advisorsPageFixture.items[0], group_id: null } },
    });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    const groupSelect = await screen.findByRole('combobox', { name: `Grupo de ${activeAgent.name}` });
    await userEvent.selectOptions(groupSelect, '');

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(`/api/v1/advisors/${activeAgent.id}`, { group_id: null })
    );
  });

  it('still offers the signup form when the manager is the only member of the organization', async () => {
    mockAgents({ 'GET /api/v1/agents': { data: { ...agentsPageFixture, items: [signedInManager], total: 1 } } });
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    expect(await screen.findByText('No hay asesores activos.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar asesor' })).toBeInTheDocument();
  });

  it('denies an AGENT session on this route', async () => {
    renderWithProviders(<AppRoutes />, { role: 'AGENT', route: '/asesores' });
    expect(await screen.findByText('No tienes acceso')).toBeInTheDocument();
  });
});
