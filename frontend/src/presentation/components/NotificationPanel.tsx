import type { ReactNode } from 'react';
import { CheckCheck } from 'lucide-react';
import type { AsyncState } from '../../application/data/use-async';
import type { NotificationsPage } from '../../application/services/notifications.service';
import { Button } from './ui/Button';
import { LoadingState } from './ui/LoadingState';
import { ErrorState } from './ui/ErrorState';
import { EmptyState } from './ui/EmptyState';
import { NotificationItem } from './NotificationItem';

type NotificationModel = NotificationsPage['items'][number];

interface NotificationPanelProps {
  state: AsyncState<NotificationsPage>;
  onSelect: (notification: NotificationModel) => void;
  onMarkAllRead: () => void;
}

// `error` is `unknown`, which an `&&` chain can't embed directly into JSX;
// an if-chain narrows it the way a ternary or && can't.
function renderBody(
  { data, error, loading, refetch }: AsyncState<NotificationsPage>,
  onSelect: (notification: NotificationModel) => void
): ReactNode {
  if (loading) return <LoadingState text="Cargando notificaciones…" />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data || data.items.length === 0) return <EmptyState text="No tienes notificaciones." />;

  return (
    <ul className="divide-y divide-slate-800/60">
      {data.items.map((notification) => (
        <NotificationItem key={notification.id} notification={notification} onSelect={onSelect} />
      ))}
    </ul>
  );
}

/** Read top to bottom as received: the API already sorts newest first, this never reorders it. */
export function NotificationPanel({ state, onSelect, onMarkAllRead }: NotificationPanelProps) {
  return (
    <div className="absolute right-0 mt-2 w-96 max-h-[28rem] flex flex-col bg-slate-900 rounded-xl border border-slate-800 shadow-xl overflow-hidden z-50">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-slate-100">Notificaciones</h2>
        {state.data && state.data.unread_count > 0 && (
          <Button variant="secondary" onClick={onMarkAllRead}>
            <CheckCheck className="w-4 h-4 inline-block mr-1.5" aria-hidden="true" />
            Marcar todas
          </Button>
        )}
      </div>

      <div className="overflow-y-auto">{renderBody(state, onSelect)}</div>
    </div>
  );
}
