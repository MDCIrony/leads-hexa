import { apiClient } from '../../infrastructure/api/api-client';
import type { components } from '../../infrastructure/api/schema';

export type NotificationsPage = components['schemas']['NotificationsPageResponse'];

/** `unread_count` travels inside this same page, not a separate endpoint. */
export async function list(limit: number, offset: number, unreadOnly?: boolean): Promise<NotificationsPage> {
  const { data } = await apiClient.get<NotificationsPage>('/api/v1/notifications', {
    params: { limit, offset, unread_only: unreadOnly },
  });
  return data;
}

export async function markAllRead(): Promise<void> {
  await apiClient.post('/api/v1/notifications/read-all');
}

export async function markRead(id: string): Promise<void> {
  await apiClient.post(`/api/v1/notifications/${id}/read`);
}
