import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { SessionContext } from '../../application/session/session-context';
import { mockApiClient } from '../../test/mock-api';
import meAgent from '../../test/fixtures/me-agent.json';
import { MfaPage } from './MfaPage';

describe('MfaPage', () => {
  it('restores the allowed destination after a verified MFA challenge', async () => {
    const refresh = vi.fn().mockResolvedValue({ ...meAgent, mfa_enabled: true });
    mockApiClient({ 'POST /api/v1/auth/mfa/verify': { data: { status: 'AUTHENTICATED' } } });

    render(
      <MemoryRouter initialEntries={[{ pathname: '/mfa', state: { from: { pathname: '/mis-leads' } } }]}>
        <SessionContext.Provider value={{ user: null, status: 'anonymous', login: vi.fn(), logout: vi.fn(), refresh }}>
          <Routes>
            <Route path="/mfa" element={<MfaPage />} />
            <Route path="/mis-leads" element={<h1>Mis leads</h1>} />
          </Routes>
        </SessionContext.Provider>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText('Código'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Verificar' }));

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Mis leads' })).toBeInTheDocument());
    expect(refresh).toHaveBeenCalledOnce();
  });
});
