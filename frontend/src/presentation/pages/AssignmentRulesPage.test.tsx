import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import assignmentRulesFixture from '../../test/fixtures/assignment-rules-page.json';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import groupsPageFixture from '../../test/fixtures/groups-page.json';
import { AssignmentRulesPage } from './AssignmentRulesPage';

const [directAgentRule] = assignmentRulesFixture.items;
const [fixtureAgent] = agentsPageFixture.items;
const [fixtureGroup] = groupsPageFixture.items;

function mockAssignmentRules(overrides: Record<string, unknown> = {}) {
  mockApiClient({
    'GET /api/v1/rules/assignment': { data: assignmentRulesFixture },
    'GET /api/v1/agents': { data: agentsPageFixture },
    'GET /api/v1/groups': { data: groupsPageFixture },
    ...overrides,
  });
}

describe('AssignmentRulesPage', () => {
  it('blocks submitting the create form without a target agent chosen', async () => {
    mockAssignmentRules();
    const postSpy = vi.spyOn(apiClient, 'post');
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(fixtureAgent.name, { selector: 'label' });
    await userEvent.type(screen.getByLabelText('Nombre'), 'Sin destino');
    await userEvent.click(screen.getByRole('button', { name: 'Crear regla' }));

    expect(await screen.findByText('Elige un grupo o al menos un asesor destino.')).toBeInTheDocument();
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('creates a rule with max_score as null, not 0, when "sin techo" is left checked', async () => {
    mockAssignmentRules();
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { ...directAgentRule, id: 'new-id' },
      status: 200,
      statusText: '',
      headers: {},
      config: {},
    } as never);
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await userEvent.type(screen.getByLabelText('Nombre'), 'Todo a un asesor');
    await userEvent.click(screen.getByRole('checkbox', { name: fixtureAgent.name }));
    await userEvent.click(screen.getByRole('button', { name: 'Crear regla' }));

    await waitFor(() =>
      expect(postSpy).toHaveBeenCalledWith(
        '/api/v1/rules/assignment',
        expect.objectContaining({ max_score: null, target_agent_ids: [fixtureAgent.id] })
      )
    );
  });

  it('shows the RULE_WITHOUT_TARGET business error if the backend still rejects it', async () => {
    mockAssignmentRules({
      'POST /api/v1/rules/assignment': {
        status: 400,
        error: { error: true, error_code: 'RULE_WITHOUT_TARGET', message: 'La regla necesita un destino.' },
      },
    });
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await userEvent.type(screen.getByLabelText('Nombre'), 'Regla');
    await userEvent.click(screen.getByRole('checkbox', { name: fixtureAgent.name }));
    await userEvent.click(screen.getByRole('button', { name: 'Crear regla' }));

    expect(await screen.findByText('La regla necesita un destino.')).toBeInTheDocument();
  });

  it('preloads an existing rule with its target agent and min/max score', async () => {
    mockAssignmentRules();
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(directAgentRule.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));

    const editForm = screen.getByRole('button', { name: 'Guardar' }).closest('div')!.parentElement as HTMLElement;
    expect(within(editForm).getByDisplayValue(directAgentRule.name)).toBeInTheDocument();
    expect(within(editForm).getByRole('checkbox', { name: fixtureAgent.name })).toBeChecked();
    expect(within(editForm).getByRole('checkbox', { name: 'Sin techo' })).toBeChecked();
  });

  it('a PATCH that only toggles is_active never touches target_agent_ids or conditions', async () => {
    mockAssignmentRules();
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(directAgentRule.name);
    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue({
      data: { ...directAgentRule, is_active: false },
      status: 200,
      statusText: '',
      headers: {},
      config: {},
    } as never);
    await userEvent.click(screen.getByRole('button', { name: 'Desactivar' }));

    await waitFor(() =>
      expect(patchSpy).toHaveBeenCalledWith(`/api/v1/rules/assignment/${directAgentRule.id}`, { is_active: false })
    );
  });

  it('names the team a rule routes to instead of calling it targetless', async () => {
    // A rule created through the API can point at a sales group. This screen
    // cannot set one, and it used to render "sin asesores" for it — a rule
    // routing every lead correctly, reading as broken.
    mockAssignmentRules({
      'GET /api/v1/rules/assignment': {
        data: {
          ...assignmentRulesFixture,
          items: [{ ...directAgentRule, target_agent_ids: [], target_group_id: fixtureGroup.id }],
        },
      },
    });
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    expect(await screen.findByText(new RegExp(`equipo ${fixtureGroup.name}`))).toBeInTheDocument();
  });

  it('lets a team-targeted rule be saved without naming any advisor', async () => {
    mockAssignmentRules({
      'GET /api/v1/rules/assignment': {
        data: {
          ...assignmentRulesFixture,
          items: [{ ...directAgentRule, target_agent_ids: [], target_group_id: fixtureGroup.id }],
        },
      },
    });
    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue({
      data: directAgentRule, status: 200, statusText: '', headers: {}, config: {},
    } as never);
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(directAgentRule.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    expect(screen.queryByText('Elige un grupo o al menos un asesor destino.')).not.toBeInTheDocument();
  });

  it('creates a rule that routes to a group, with no agent named', async () => {
    mockAssignmentRules({ 'POST /api/v1/rules/assignment': { status: 201, data: directAgentRule } });
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByRole('option', { name: fixtureGroup.name });
    await userEvent.type(screen.getByLabelText('Nombre'), 'Todo al equipo');
    await userEvent.selectOptions(screen.getByLabelText('Grupo destino'), fixtureGroup.id);
    await userEvent.click(screen.getByRole('button', { name: 'Crear regla' }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/rules/assignment',
        expect.objectContaining({ target_group_id: fixtureGroup.id, target_agent_ids: [] })
      )
    );
  });

  it('moves an agent-targeted rule to a group on edit', async () => {
    mockAssignmentRules({ [`PATCH /api/v1/rules/assignment/${directAgentRule.id}`]: { data: directAgentRule } });
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(directAgentRule.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const [, editGroupSelect] = screen.getAllByLabelText('Grupo destino');
    await userEvent.selectOptions(editGroupSelect, fixtureGroup.id);
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith(
        `/api/v1/rules/assignment/${directAgentRule.id}`,
        expect.objectContaining({ target_group_id: fixtureGroup.id })
      )
    );
  });

  it('offers no "Sin grupo" when editing a group-targeted rule: the PATCH cannot remove it', async () => {
    mockAssignmentRules({
      'GET /api/v1/rules/assignment': {
        data: { ...assignmentRulesFixture, items: [{ ...directAgentRule, target_agent_ids: [], target_group_id: fixtureGroup.id }] },
      },
    });
    renderWithProviders(<AssignmentRulesPage />, { role: 'MANAGER' });

    await screen.findByText(directAgentRule.name);
    await userEvent.click(screen.getByRole('button', { name: 'Editar' }));
    const [, editGroupSelect] = screen.getAllByLabelText('Grupo destino');

    expect(editGroupSelect).toHaveValue(fixtureGroup.id);
    expect(within(editGroupSelect).queryByRole('option', { name: 'Sin grupo' })).not.toBeInTheDocument();
  });
});
