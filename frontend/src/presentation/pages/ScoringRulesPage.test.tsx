import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import scoringRulesFixture from '../../test/fixtures/scoring-rules-page.json';
import { ScoringRulesPage } from './ScoringRulesPage';

const [budgetRule] = scoringRulesFixture.items;

function mockScoringRules(overrides: Record<string, unknown> = {}) {
  mockApiClient({
    'GET /api/v1/rules/scoring': { data: scoringRulesFixture },
    ...overrides,
  });
}

describe('ScoringRulesPage', () => {
  it('lists rules in the order the API returned, by priority', async () => {
    mockScoringRules();
    renderWithProviders(<ScoringRulesPage />, { role: 'MANAGER' });

    const names = (await screen.findAllByRole('heading', { level: 4 })).map((h) => h.textContent);
    expect(names).toEqual(scoringRulesFixture.items.map((r) => r.name));
  });

  it('creates a rule with a real conditions[] array, not a flat field', async () => {
    mockScoringRules();
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { ...budgetRule, id: 'new-id' },
      status: 200,
      statusText: '',
      headers: {},
      config: {},
    } as never);
    renderWithProviders(<ScoringRulesPage />, { role: 'MANAGER' });

    await screen.findByText(budgetRule.name);
    await userEvent.type(screen.getByLabelText('Nombre'), 'Alta prioridad');
    await userEvent.type(screen.getByPlaceholderText('campo, ej. budget'), 'budget');
    await userEvent.type(screen.getByPlaceholderText('valor'), '9000');
    await userEvent.click(screen.getByRole('button', { name: 'Crear regla' }));

    await waitFor(() =>
      expect(postSpy).toHaveBeenCalledWith(
        '/api/v1/rules/scoring',
        expect.objectContaining({
          conditions: [{ field: 'budget', operator: 'GREATER_THAN', value: 9000 }],
        })
      )
    );
  });

  it('toggling active sends only is_active, never the whole rule', async () => {
    mockScoringRules();
    renderWithProviders(<ScoringRulesPage />, { role: 'MANAGER' });

    await screen.findByText(budgetRule.name);
    const toggleButton = screen.getAllByRole('button', { name: 'Desactivar' })[0];
    const patchSpy = vi.spyOn(apiClient, 'patch').mockResolvedValue({
      data: { ...budgetRule, is_active: false },
      status: 200,
      statusText: '',
      headers: {},
      config: {},
    } as never);
    await userEvent.click(toggleButton);

    await waitFor(() =>
      expect(patchSpy).toHaveBeenCalledWith(`/api/v1/rules/scoring/${budgetRule.id}`, { is_active: false })
    );
  });

  it('preloads an existing rule with its current values when editing', async () => {
    mockScoringRules();
    renderWithProviders(<ScoringRulesPage />, { role: 'MANAGER' });

    await screen.findByText(budgetRule.name);
    await userEvent.click(screen.getAllByRole('button', { name: 'Editar' })[0]);

    const editForm = screen.getByRole('button', { name: 'Guardar' }).closest('div')!.parentElement as HTMLElement;
    expect(within(editForm).getByDisplayValue(budgetRule.name)).toBeInTheDocument();
    expect(within(editForm).getByDisplayValue(String(budgetRule.score_delta))).toBeInTheDocument();
    expect(within(editForm).getByDisplayValue(budgetRule.conditions[0].field)).toBeInTheDocument();
  });

  it('a delete requires confirmation and reassures that scored leads keep their breakdown', async () => {
    mockScoringRules();
    renderWithProviders(<ScoringRulesPage />, { role: 'MANAGER' });

    await screen.findByText(budgetRule.name);
    await userEvent.click(screen.getAllByRole('button', { name: 'Borrar' })[0]);

    expect(screen.getByText(/conservan su desglose/)).toBeInTheDocument();
    const deleteSpy = vi.spyOn(apiClient, 'delete').mockResolvedValue({
      data: undefined,
      status: 204,
      statusText: '',
      headers: {},
      config: {},
    } as never);
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar borrado' }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(`/api/v1/rules/scoring/${budgetRule.id}`));
  });
});
