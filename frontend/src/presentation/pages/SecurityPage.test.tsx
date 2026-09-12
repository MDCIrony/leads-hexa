import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { SessionContext } from '../../application/session/session-context';
import { apiClient } from '../../infrastructure/api/api-client';
import { mockApiClient } from '../../test/mock-api';
import meAgent from '../../test/fixtures/me-agent.json';
import { SecurityPage } from './SecurityPage';

describe('SecurityPage', () => {
  it('regenerates recovery codes with both required factors', async () => {
    const user = { ...meAgent, mfa_enabled: true };
    mockApiClient({
      'POST /api/v1/auth/mfa/recovery-codes/regenerate': { data: { recovery_codes: ['new-recovery-code'] } },
    });
    const postSpy = vi.spyOn(apiClient, 'post');

    render(
      <MemoryRouter>
        <SessionContext.Provider value={{ user, status: 'authenticated', login: vi.fn(), logout: vi.fn(), refresh: vi.fn() }}>
          <SecurityPage />
        </SessionContext.Provider>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText('Contraseña'), 'Secret123');
    await userEvent.type(screen.getByLabelText('Código de autenticación o recuperación'), '123456');
    await userEvent.click(screen.getByRole('button', { name: 'Regenerar códigos' }));

    await waitFor(() => expect(screen.getByText('new-recovery-code')).toBeInTheDocument());
    expect(postSpy).toHaveBeenCalledWith('/api/v1/auth/mfa/recovery-codes/regenerate', {
      password: 'Secret123',
      code: '123456',
    });
  });

  it('shows a wrong password inline without leaving the page', async () => {
    const user = { ...meAgent, mfa_enabled: false };
    mockApiClient({
      'POST /api/v1/auth/mfa/setup': {
        status: 401,
        error: { error: true, error_code: 'INVALID_CREDENTIALS', message: 'Invalid authentication factor' },
      },
    });
    const logout = vi.fn();

    render(
      <MemoryRouter>
        <SessionContext.Provider value={{ user, status: 'authenticated', login: vi.fn(), logout, refresh: vi.fn() }}>
          <SecurityPage />
        </SessionContext.Provider>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText('Contraseña'), 'wrong-pass');
    await userEvent.click(screen.getByRole('button', { name: 'Configurar MFA' }));

    await waitFor(() => expect(screen.getByText('Contraseña incorrecta.')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Configurar MFA' })).toBeInTheDocument();
    expect(logout).not.toHaveBeenCalled();
  });

  it('shows a wrong confirmation code inline', async () => {
    const user = { ...meAgent, mfa_enabled: false };
    mockApiClient({
      'POST /api/v1/auth/mfa/setup': { data: { secret: 'SECRET', otpauth_uri: 'otpauth://totp/x?secret=SECRET' } },
      'POST /api/v1/auth/mfa/setup/confirm': {
        status: 401,
        error: { error: true, error_code: 'INVALID_CREDENTIALS', message: 'Invalid authentication factor' },
      },
    });

    render(
      <MemoryRouter>
        <SessionContext.Provider value={{ user, status: 'authenticated', login: vi.fn(), logout: vi.fn(), refresh: vi.fn() }}>
          <SecurityPage />
        </SessionContext.Provider>
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText('Contraseña'), 'Secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Configurar MFA' }));
    await waitFor(() => expect(screen.getByLabelText('Código de confirmación')).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText('Código de confirmación'), '000000');
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }));

    await waitFor(() => expect(screen.getByText('Código inválido.')).toBeInTheDocument());
  });
});
