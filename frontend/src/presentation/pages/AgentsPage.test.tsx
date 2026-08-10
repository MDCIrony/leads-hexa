import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosHeaders, type AxiosResponse } from 'axios';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import groupsPageFixture from '../../test/fixtures/groups-page.json';
import { AgentsPage } from './AgentsPage';
import { AppRoutes } from '../routes/app-routes';

const [activeAgent] = agentsPageFixture.items;
const inactiveAgent = { ...agentsPageFixture.items[1], is_active: false };
const mixedFixture = { ...agentsPageFixture, items: [activeAgent, inactiveAgent] };

function fakeResponse<T>(data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

function mockAgentsAndGroups(overrides: Record<string, unknown> = {}) {
  mockApiClient({
    'GET /api/v1/agents': { data: mixedFixture },
    'GET /api/v1/groups': { data: groupsPageFixture },
    ...overrides,
  });
}

describe('AgentsPage', () => {
  it('deactivates through DELETE, with a warning instead of the word "eliminar"', async () => {
    mockAgentsAndGroups();
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
    mockAgentsAndGroups();
    renderWithProviders(<AgentsPage />, { role: 'MANAGER' });

    const reactivateButton = await screen.findByRole('button', { name: 'Reactivar' });

    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue(fakeResponse({ ...inactiveAgent, is_active: true }));
    await userEvent.click(reactivateButton);

    await waitFor(() =>
      expect(patchSpy).toHaveBeenCalledWith(`/api/v1/agents/${inactiveAgent.id}`, { is_active: true })
    );
  });

  it('shows EMAIL_ALREADY_EXISTS as the message from a duplicate signup', async () => {
    mockAgentsAndGroups({
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

  it('denies an AGENT session on this route', async () => {
    renderWithProviders(<AppRoutes />, { role: 'AGENT', route: '/asesores' });
    expect(await screen.findByText('No tienes acceso')).toBeInTheDocument();
  });
});
