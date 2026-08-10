import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import notificationsPage from '../../test/fixtures/notifications-page.json';
import { list, markAllRead, markRead } from './notifications.service';

describe('notifications.list', () => {
  it('carries unread_count inside the same page, not a separate call', async () => {
    mockApiClient({ 'GET /api/v1/notifications': { data: notificationsPage } });

    const page = await list(20, 0);

    expect(page.unread_count).toBe(notificationsPage.unread_count);
    expect(page.items).toHaveLength(1);
  });
});

describe('notifications.markAllRead and notifications.markRead', () => {
  it('resolve without a body on the 204 responses', async () => {
    const notificationId = notificationsPage.items[0].id;
    mockApiClient({
      'POST /api/v1/notifications/read-all': { status: 204, data: undefined },
      [`POST /api/v1/notifications/${notificationId}/read`]: { status: 204, data: undefined },
    });

    await expect(markAllRead()).resolves.toBeUndefined();
    await expect(markRead(notificationId)).resolves.toBeUndefined();
  });
});
