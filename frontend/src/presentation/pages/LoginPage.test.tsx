import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import { SessionProvider } from '../../application/session/session-context';
import { mockApiClient } from '../../test/mock-api';
import { AppRoutes } from '../routes/app-routes';
import loginFixture from '../../test/fixtures/login.json';
import meAdmin from '../../test/fixtures/me-admin.json';
import meManager from '../../test/fixtures/me-manager.json';
import meAgent from '../../test/fixtures/me-agent.json';
import { LoginPage } from './LoginPage';

async function fillAndSubmit(email: string, password: string) {
  await userEvent.type(screen.getByLabelText('Correo'), email);
  await userEvent.type(screen.getByLabelText('Contraseña'), password);
  await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
}

// Renders the whole route tree, not just LoginPage: which panel a role lands
// on is a routing decision (RootRedirect), not something LoginPage decides.
function renderApp(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <SessionProvider>
        <AppRoutes />
      </SessionProvider>
    </MemoryRouter>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    mockApiClient({
      'GET /api/v1/auth/me': {
        status: 401,
        error: { error: true, error_code: 'UNAUTHORIZED', message: 'No autenticado.' },
      },
    });
  });

  it('shows the bootstrap notice passed via location state, without touching the session', async () => {
    render(
      <MemoryRouter
        initialEntries={[{ pathname: '/login', state: { notice: 'La plataforma ya tiene un administrador.' } }]}
      >
        <SessionProvider>
          <LoginPage />
        </SessionProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText('La plataforma ya tiene un administrador.')).toBeInTheDocument();
  });

  it.each([
    ['ADMIN', meAdmin, 'Organizaciones'],
    ['MANAGER', meManager, 'Asesores'],
    ['AGENT', meAgent, 'Mis leads'],
  ] as const)('lands %s on its own panel after login', async (_role, meFixture, panelTitle) => {
    mockApiClient({
      'POST /api/v1/auth/login': { data: loginFixture },
      'GET /api/v1/auth/me': {
        responses: [
          { status: 401, error: { error: true, error_code: 'UNAUTHORIZED', message: 'No autenticado.' } },
          { data: meFixture },
        ],
      },
    });
    renderApp('/login');

    await fillAndSubmit(meFixture.email, 'Secret123');

    await waitFor(() => expect(screen.getByRole('heading', { name: panelTitle })).toBeInTheDocument());
  });

  it('returns to the protected route it redirected from once logged in', async () => {
    mockApiClient({
      'POST /api/v1/auth/login': { data: loginFixture },
      'GET /api/v1/auth/me': {
        responses: [
          { status: 401, error: { error: true, error_code: 'UNAUTHORIZED', message: 'No autenticado.' } },
          { data: meAgent },
        ],
      },
    });
    renderApp('/mis-leads');

    await waitFor(() => expect(screen.getByLabelText('Correo')).toBeInTheDocument());
    await fillAndSubmit(meAgent.email, 'Secret123');

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Mis leads' })).toBeInTheDocument());
  });

  it('discards a pending destination the new session cannot reach, landing on its own panel instead', async () => {
    // A manager's session redirected to /login from /asesores (e.g. it
    // expired there); an agent logs in on the same tab afterwards. Honoring
    // that leftover `from` would drop the agent straight onto a forbidden
    // page as the first thing a brand-new session shows.
    mockApiClient({
      'POST /api/v1/auth/login': { data: loginFixture },
      'GET /api/v1/auth/me': {
        responses: [
          { status: 401, error: { error: true, error_code: 'UNAUTHORIZED', message: 'No autenticado.' } },
          { data: meAgent },
        ],
      },
    });
    render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state: { from: { pathname: '/asesores' } } }]}>
        <SessionProvider>
          <AppRoutes />
        </SessionProvider>
      </MemoryRouter>
    );

    await fillAndSubmit(meAgent.email, 'Secret123');

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Mis leads' })).toBeInTheDocument());
    expect(screen.queryByText('No tienes acceso')).not.toBeInTheDocument();
  });

  it('declares autocomplete on both fields so the browser stops warning about it', async () => {
    renderApp('/login');

    expect(await screen.findByLabelText('Correo')).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password');
  });

  it('shows the same message for an unknown email as for a wrong password', async () => {
    const invalidCredentials = {
      error: true as const,
      error_code: 'INVALID_CREDENTIALS',
      message: 'El correo o la contraseña no coinciden.',
    };
    mockApiClient({
      'POST /api/v1/auth/login': { status: 401, error: invalidCredentials },
      'GET /api/v1/auth/me': {
        status: 401,
        error: { error: true, error_code: 'UNAUTHORIZED', message: 'No autenticado.' },
      },
    });
    renderApp('/login');

    await fillAndSubmit('unknown@plat.test', 'whatever');

    await waitFor(() => expect(screen.getByText(invalidCredentials.message)).toBeInTheDocument());
  });
});
