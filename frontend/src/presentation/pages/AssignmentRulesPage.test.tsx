import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import assignmentRulesFixture from '../../test/fixtures/assignment-rules-page.json';
import agentsPageFixture from '../../test/fixtures/agents-page.json';
import { AssignmentRulesPage } from './AssignmentRulesPage';

const [directAgentRule] = assignmentRulesFixture.items;
const [fixtureAgent] = agentsPageFixture.items;

function mockAssignmentRules(overrides: Record<string, unknown> = {}) {
  mockApiClient({
    'GET /api/v1/rules/assignment': { data: assignmentRulesFixture },
    'GET /api/v1/agents': { data: agentsPageFixture },
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

    expect(await screen.findByText('Elige al menos un asesor destino.')).toBeInTheDocument();
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
});
