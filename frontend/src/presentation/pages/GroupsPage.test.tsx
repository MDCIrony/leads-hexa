import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import groupsPageFixture from '../../test/fixtures/groups-page.json';
import advisorsPageFixture from '../../test/fixtures/advisors-page.json';
import { GroupsPage } from './GroupsPage';
import { AppRoutes } from '../routes/app-routes';

const [fixtureGroup] = groupsPageFixture.items;
const [member] = advisorsPageFixture.items;

function mockGroups(overrides: Record<string, unknown> = {}) {
  mockApiClient({ 'GET /api/v1/groups': { data: groupsPageFixture }, ...overrides });
}

describe('GroupsPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('creates a group with no capacity sent as null, not 0', async () => {
    mockGroups({ 'POST /api/v1/groups': { status: 201, data: fixtureGroup } });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureGroup.name);
    await userEvent.type(screen.getByLabelText('Nombre del grupo'), 'Enterprise');
    await userEvent.selectOptions(screen.getByLabelText('Estrategia por defecto'), 'ROUND_ROBIN');
    await userEvent.click(screen.getByRole('button', { name: 'Crear grupo' }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/groups', {
        name: 'Enterprise',
        description: null,
        default_strategy: 'ROUND_ROBIN',
        capacity_per_agent: null,
      })
    );
  });

  it('shows GROUP_ALREADY_EXISTS on the name field', async () => {
    mockGroups({
      'POST /api/v1/groups': {
        status: 400,
        error: { error: true, error_code: 'GROUP_ALREADY_EXISTS', message: 'Ya existe un grupo con ese nombre.' },
      },
    });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await userEvent.type(screen.getByLabelText('Nombre del grupo'), fixtureGroup.name);
    await userEvent.click(screen.getByRole('button', { name: 'Crear grupo' }));

    expect(await screen.findByText('Ya existe un grupo con ese nombre.')).toBeInTheDocument();
  });

  it('edits a group preloaded with its values through PATCH', async () => {
    mockGroups({ [`PATCH /api/v1/groups/${fixtureGroup.id}`]: { data: { ...fixtureGroup, capacity_per_agent: 5 } } });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureGroup.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    expect(screen.getByDisplayValue(fixtureGroup.name)).toBeInTheDocument();
    await userEvent.type(screen.getAllByLabelText('Capacidad por asesor')[1], '5');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(
        `/api/v1/groups/${fixtureGroup.id}`,
        expect.objectContaining({ name: fixtureGroup.name, capacity_per_agent: 5 })
      )
    );
  });

  it('does not offer to clear a capacity the API cannot clear', async () => {
    mockGroups({ 'GET /api/v1/groups': { data: { ...groupsPageFixture, items: [{ ...fixtureGroup, capacity_per_agent: 3 }] } } });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureGroup.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    expect(screen.getByLabelText('Capacidad por asesor (se puede cambiar, no quitar)')).toBeRequired();
  });

  it('deletes only after confirming', async () => {
    mockGroups({ [`DELETE /api/v1/groups/${fixtureGroup.id}`]: { status: 204, data: undefined } });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureGroup.name);
    await userEvent.click(screen.getByRole('button', { name: 'Borrar' }));
    expect(apiClient.delete).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar borrado' }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith(`/api/v1/groups/${fixtureGroup.id}`));
  });

  it('lists a group\'s members from /advisors filtered by group_id', async () => {
    mockGroups({ 'GET /api/v1/advisors': { data: { ...advisorsPageFixture, items: [member], total: 1 } } });
    renderWithProviders(<GroupsPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureGroup.name);
    await userEvent.click(screen.getByRole('button', { name: 'Ver miembros' }));

    expect(await screen.findByText(member.name)).toBeInTheDocument();
    const params = vi.mocked(apiClient.get).mock.calls.find(([url]) => url === '/api/v1/advisors')?.[1]?.params;
    expect(params).toMatchObject({ group_id: fixtureGroup.id });
  });

  it('denies an AGENT session on this route', async () => {
    mockGroups();
    renderWithProviders(<AppRoutes />, { role: 'AGENT', route: '/grupos' });
    expect(await screen.findByText('No tienes acceso')).toBeInTheDocument();
  });
});
