import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { mockApiClient } from '../../test/mock-api';
import meAdmin from '../../test/fixtures/me-admin.json';
import { BootstrapPage } from './BootstrapPage';

/** Stands in for LoginPage: exposes what BootstrapPage actually hands it, without pulling in the whole route tree. */
function LoginLandingSpy() {
  const location = useLocation();
  const notice = (location.state as { notice?: string } | null)?.notice;
  return <p>login screen{notice ? ` — ${notice}` : ''}</p>;
}

function renderBootstrap() {
  return render(
    <MemoryRouter initialEntries={['/bootstrap']}>
      <Routes>
        <Route path="/bootstrap" element={<BootstrapPage />} />
        <Route path="/login" element={<LoginLandingSpy />} />
      </Routes>
    </MemoryRouter>
  );
}

async function fillAndSubmit() {
  await userEvent.type(screen.getByLabelText('Nombre'), meAdmin.name);
  await userEvent.type(screen.getByLabelText('Correo'), meAdmin.email);
  await userEvent.type(screen.getByLabelText('Contraseña'), 'Secret123');
  await userEvent.click(screen.getByRole('button', { name: 'Crear administrador' }));
}

describe('BootstrapPage', () => {
  it('creates the admin and moves to login without signing in', async () => {
    mockApiClient({ 'POST /api/v1/agents': { status: 201, data: meAdmin } });
    renderBootstrap();

    await fillAndSubmit();

    await waitFor(() => expect(screen.getByText('login screen')).toBeInTheDocument());
  });

  it('treats a 401 as "already bootstrapped", not an expired session', async () => {
    mockApiClient({
      'POST /api/v1/agents': {
        status: 401,
        error: { error: true, error_code: 'UNAUTHORIZED', message: 'Not authenticated' },
      },
    });
    renderBootstrap();

    await fillAndSubmit();

    await waitFor(() =>
      expect(screen.getByText(/login screen — La plataforma ya tiene un administrador/)).toBeInTheDocument()
    );
  });

  it('surfaces EMAIL_ALREADY_EXISTS on a repeated email', async () => {
    const emailTaken = {
      error: true as const,
      error_code: 'EMAIL_ALREADY_EXISTS',
      message: 'Ya existe un agente con ese correo.',
    };
    mockApiClient({ 'POST /api/v1/agents': { status: 400, error: emailTaken } });
    renderBootstrap();

    await fillAndSubmit();

    expect(await screen.findByText(emailTaken.message)).toBeInTheDocument();
  });
});
