import { describe, expect, it } from 'vitest';
import { mockApiClient } from '../../test/mock-api';
import type { components } from '../../infrastructure/api/schema';
import { list, markAllRead, markRead } from './notifications.service';

// No captured fixture exists yet — typed literal against NotificationsPageResponse.
const notificationsPage: components['schemas']['NotificationsPageResponse'] = {
  items: [
    {
      id: 'c3c3c3c3-0000-0000-0000-000000000001',
      kind: 'LEAD_ASSIGNED',
      message: 'Se te asignó un lead',
      lead_id: 'a407baf0-9597-4073-b95b-db6686ee6f0c',
      intake_record_id: null,
      is_read: false,
      created_at: '2026-08-10T19:01:07.777632+00:00',
    },
  ],
  total: 1,
  limit: 20,
  offset: 0,
  has_more: false,
  unread_count: 1,
};

describe('notifications.list', () => {
  it('carries unread_count inside the same page, not a separate call', async () => {
    mockApiClient({ 'GET /api/v1/notifications': { data: notificationsPage } });

    const page = await list(20, 0);

    expect(page.unread_count).toBe(1);
    expect(page.items).toHaveLength(1);
  });
});

describe('notifications.markAllRead and notifications.markRead', () => {
  it('resolve without a body on the 204 responses', async () => {
    mockApiClient({
      'POST /api/v1/notifications/read-all': { status: 204, data: undefined },
      'POST /api/v1/notifications/c3c3c3c3-0000-0000-0000-000000000001/read': { status: 204, data: undefined },
    });

    await expect(markAllRead()).resolves.toBeUndefined();
    await expect(markRead('c3c3c3c3-0000-0000-0000-000000000001')).resolves.toBeUndefined();
  });
});
