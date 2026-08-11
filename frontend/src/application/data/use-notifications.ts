import { useCallback, useState } from 'react';
import { useAsync, type AsyncState } from './use-async';
import { list, markAllRead, markRead, type NotificationsPage } from '../services/notifications.service';

const PAGE_SIZE = 20;

const EMPTY_PAGE: NotificationsPage = {
  items: [],
  total: 0,
  limit: PAGE_SIZE,
  offset: 0,
  has_more: false,
  unread_count: 0,
};

export interface UseNotificationsResult {
  open: boolean;
  toggle: () => void;
  close: () => void;
  state: AsyncState<NotificationsPage>;
  markOneRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
}

/**
 * Fetches only when the panel opens, and again after a mark-as-read — never
 * on a timer. The closed state resolves to a local empty page instead of
 * calling the API, which is what keeps the bell's badge silent until the
 * user has actually opened the panel once.
 */
export function useNotifications(): UseNotificationsResult {
  const [open, setOpen] = useState(false);
  const state = useAsync<NotificationsPage>(() => (open ? list(PAGE_SIZE, 0) : Promise.resolve(EMPTY_PAGE)), [open]);
  const { refetch } = state;

  const toggle = useCallback(() => setOpen((wasOpen) => !wasOpen), []);
  const close = useCallback(() => setOpen(false), []);

  const markOneRead = useCallback(
    async (id: string) => {
      await markRead(id);
      refetch();
    },
    [refetch]
  );

  const markAllAsRead = useCallback(async () => {
    await markAllRead();
    refetch();
  }, [refetch]);

  return { open, toggle, close, state, markOneRead, markAllAsRead };
}
