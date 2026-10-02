import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { apiClient } from '../../infrastructure/api/api-client';
import { renderWithProviders } from '../../test/render';
import { mockApiClient } from '../../test/mock-api';
import tenantsPageFixture from '../../test/fixtures/tenants-page.json';
import { OrganizationsPage } from './OrganizationsPage';
import { AppRoutes } from '../routes/app-routes';

const createdTenant = {
  ...tenantsPageFixture.items[0],
  id: 'new-tenant-id',
  name: 'Acme',
  manager: { id: 'mgr-1', name: 'Ana', email: 'ana@acme.test', role: 'MANAGER', is_active: true },
};

async function fillAndSubmit() {
  await userEvent.type(screen.getByLabelText('Nombre de la organización'), 'Acme');
  await userEvent.type(screen.getByLabelText('Nombre del gestor'), 'Ana');
  await userEvent.type(screen.getByLabelText('Correo del gestor'), 'ana@acme.test');
  await userEvent.type(screen.getByLabelText('Contraseña del gestor'), 'Secret123');
  await userEvent.click(screen.getByRole('button', { name: 'Crear organización' }));
}

describe('OrganizationsPage', () => {
  it('sends the manager nested under `manager`, not at the root of the body', async () => {
    mockApiClient({
      'GET /api/v1/tenants': { data: tenantsPageFixture },
      'POST /api/v1/tenants': { status: 201, data: createdTenant },
    });
    renderWithProviders(<OrganizationsPage />, { role: 'ADMIN' });
    await screen.findByText(tenantsPageFixture.items[0].name);

    const postSpy = vi.spyOn(apiClient, 'post');
    await fillAndSubmit();

    await waitFor(() => expect(postSpy).toHaveBeenCalled());
    const [, body] = postSpy.mock.calls[0];
    expect(body).toMatchObject({
      name: 'Acme',
      manager: { name: 'Ana', email: 'ana@acme.test', password: 'Secret123' },
    });
    expect((body as Record<string, unknown>).manager_email).toBeUndefined();
  });

  it("shows the created manager's email after signup — the only time it's shown", async () => {
    mockApiClient({
      'GET /api/v1/tenants': { data: tenantsPageFixture },
      'POST /api/v1/tenants': { status: 201, data: createdTenant },
    });
    renderWithProviders(<OrganizationsPage />, { role: 'ADMIN' });
    await screen.findByText(tenantsPageFixture.items[0].name);

    await fillAndSubmit();

    expect(await screen.findByText('ana@acme.test')).toBeInTheDocument();
  });

  it('shows TENANT_ALREADY_EXISTS on the name field', async () => {
    mockApiClient({
      'GET /api/v1/tenants': { data: tenantsPageFixture },
      'POST /api/v1/tenants': {
        status: 400,
        error: { error: true, error_code: 'TENANT_ALREADY_EXISTS', message: 'Ya existe una organización con ese nombre' },
      },
    });
    renderWithProviders(<OrganizationsPage />, { role: 'ADMIN' });
    await screen.findByText(tenantsPageFixture.items[0].name);

    await fillAndSubmit();
    expect(await screen.findByText('Ya existe una organización con ese nombre')).toBeInTheDocument();
  });

  it('shows EMAIL_ALREADY_EXISTS on the manager email field, with a different message', async () => {
    mockApiClient({
      'GET /api/v1/tenants': { data: tenantsPageFixture },
      'POST /api/v1/tenants': {
        status: 400,
        error: { error: true, error_code: 'EMAIL_ALREADY_EXISTS', message: 'Ya existe un usuario con ese correo electrónico' },
      },
    });
    renderWithProviders(<OrganizationsPage />, { role: 'ADMIN' });
    await screen.findByText(tenantsPageFixture.items[0].name);

    await fillAndSubmit();
    expect(await screen.findByText(/en otra organización de la plataforma/)).toBeInTheDocument();
    expect(screen.queryByText('Ya existe una organización con ese nombre')).not.toBeInTheDocument();
  });

  it("paints the envelope's items and respects has_more", async () => {
    mockApiClient({ 'GET /api/v1/tenants': { data: tenantsPageFixture } });
    renderWithProviders(<OrganizationsPage />, { role: 'ADMIN' });

    for (const tenant of tenantsPageFixture.items) {
      expect(await screen.findByText(tenant.name)).toBeInTheDocument();
    }
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
  });

  it('denies a MANAGER session on this route', async () => {
    renderWithProviders(<AppRoutes />, { role: 'MANAGER', route: '/admin/organizaciones' });
    expect(await screen.findByText('No tienes acceso')).toBeInTheDocument();
  });
});
