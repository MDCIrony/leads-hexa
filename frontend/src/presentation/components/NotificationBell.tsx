import { Bell } from 'lucide-react';
import { useNavigate } from 'react-router';
import { useNotifications } from '../../application/data/use-notifications';
import { useSession } from '../../application/session/use-session';
import type { NotificationsPage } from '../../application/services/notifications.service';
import { NotificationPanel } from './NotificationPanel';

type NotificationModel = NotificationsPage['items'][number];

/** Its own component per the 150-line limit: Header stays a shell, this owns the bell's open/read state. */
export function NotificationBell() {
  const { user } = useSession();
  const navigate = useNavigate();
  const { open, toggle, close, state, markOneRead, markAllAsRead } = useNotifications();
  const unreadCount = state.data?.unread_count ?? 0;

  function handleSelect(notification: NotificationModel) {
    if (!notification.is_read) {
      void markOneRead(notification.id);
    }
    // A manager or admin can also receive notifications, but only an agent has a "my leads" detail to land on.
    if (notification.lead_id && user?.role === 'AGENT') {
      close();
      navigate(`/mis-leads/${notification.lead_id}`);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={toggle}
        aria-label={unreadCount > 0 ? `Notificaciones, ${unreadCount} sin leer` : 'Notificaciones'}
        className="relative p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-4 px-1 rounded-full bg-rose-600 text-slate-100 text-[10px] font-bold flex items-center justify-center"
          >
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={close} />
          <NotificationPanel state={state} onSelect={handleSelect} onMarkAllRead={() => void markAllAsRead()} />
        </>
      )}
    </div>
  );
}
