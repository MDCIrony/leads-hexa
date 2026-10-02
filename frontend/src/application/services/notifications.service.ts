import { apiClient } from '../../infrastructure/api/api-client';

// Hand-written: notifications owns this contract (F2) but the gateway does not publish its
// OpenAPI yet, so gen:api cannot generate it. Replace with a third generated file when it does.
export interface NotificationsPage {
  items: {
    id: string;
    kind: string;
    message: string;
    lead_id?: string | null;
    intake_record_id?: string | null;
    is_read: boolean;
    created_at: string;
  }[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  unread_count: number;
}

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
