import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import { SessionContext } from '../../application/session/session-context';
import { mockApiClient } from '../../test/mock-api';
import notificationsPage from '../../test/fixtures/notifications-page.json';
import meAgent from '../../test/fixtures/me-agent.json';
import meManager from '../../test/fixtures/me-manager.json';
import { NotificationBell } from './NotificationBell';

const EMPTY_PAGE = { items: [], total: 0, limit: 20, offset: 0, has_more: false, unread_count: 0 };

function renderBell(user: typeof meAgent | typeof meManager) {
  return render(
    <MemoryRouter initialEntries={['/mis-leads']}>
      <SessionContext.Provider value={{ user, status: 'authenticated', login: vi.fn(), logout: vi.fn() }}>
        <Routes>
          <Route path="/mis-leads" element={<NotificationBell />} />
          <Route path="/mis-leads/:leadId" element={<p>Detalle del lead</p>} />
        </Routes>
      </SessionContext.Provider>
    </MemoryRouter>
  );
}

async function openPanel() {
  await userEvent.click(screen.getByRole('button', { name: /Notificaciones/ }));
}

describe('NotificationBell', () => {
  it('reflects the unread count on the badge once the panel is opened', async () => {
    mockApiClient({ 'GET /api/v1/notifications': { data: notificationsPage } });
    renderBell(meAgent);

    await openPanel();

    expect(await screen.findByText(String(notificationsPage.unread_count))).toBeInTheDocument();
    expect(screen.getByText(notificationsPage.items[0].message)).toBeInTheDocument();
  });

  it('shows no badge number when nothing is unread', async () => {
    mockApiClient({ 'GET /api/v1/notifications': { data: EMPTY_PAGE } });
    renderBell(meAgent);

    await openPanel();

    expect(await screen.findByText('No tienes notificaciones.')).toBeInTheDocument();
    expect(screen.queryByLabelText(/sin leer/)).not.toBeInTheDocument();
  });

  it('marks a notification as read when clicked, which clears the badge', async () => {
    const notification = notificationsPage.items[0];
    mockApiClient({
      'GET /api/v1/notifications': { data: notificationsPage },
      [`POST /api/v1/notifications/${notification.id}/read`]: { status: 204, data: undefined },
    });
    renderBell(meAgent);
    await openPanel();
    await screen.findByText(notification.message);

    // The click triggers a refetch: script it to reflect the now-read state.
    mockApiClient({
      'GET /api/v1/notifications': {
        data: { ...notificationsPage, unread_count: 0, items: [{ ...notification, is_read: true }] },
      },
      [`POST /api/v1/notifications/${notification.id}/read`]: { status: 204, data: undefined },
    });
    await userEvent.click(screen.getByText(notification.message));

    await waitFor(() => expect(screen.queryByText('1')).not.toBeInTheDocument());
  });

  it("takes an agent to the lead's detail when the notification carries one", async () => {
    const notification = notificationsPage.items[0];
    mockApiClient({
      'GET /api/v1/notifications': { data: notificationsPage },
      [`POST /api/v1/notifications/${notification.id}/read`]: { status: 204, data: undefined },
    });
    renderBell(meAgent);
    await openPanel();

    await userEvent.click(await screen.findByText(notification.message));

    expect(await screen.findByText('Detalle del lead')).toBeInTheDocument();
  });

  it('does not navigate for a role other than agent', async () => {
    const notification = notificationsPage.items[0];
    mockApiClient({
      'GET /api/v1/notifications': { data: notificationsPage },
      [`POST /api/v1/notifications/${notification.id}/read`]: { status: 204, data: undefined },
    });
    renderBell(meManager);
    await openPanel();

    await userEvent.click(await screen.findByText(notification.message));

    expect(screen.queryByText('Detalle del lead')).not.toBeInTheDocument();
  });
});
