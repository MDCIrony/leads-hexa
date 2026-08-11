import { Ban, Repeat, UserPlus, UserX } from 'lucide-react';
import type { NotificationsPage } from '../../application/services/notifications.service';

type NotificationModel = NotificationsPage['items'][number];

type Tone = 'purple' | 'blue' | 'amber' | 'rose';

const TONE_CLASSES: Record<Tone, string> = {
  purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  rose: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
};

// An intake rejection must not read like a routine assignment: each kind
// gets its own icon and tone, not just its own text.
function iconFor(kind: string): { icon: typeof UserPlus; tone: Tone } {
  switch (kind) {
    case 'LEAD_ASSIGNED':
      return { icon: UserPlus, tone: 'purple' };
    case 'LEAD_REASSIGNED':
      return { icon: Repeat, tone: 'blue' };
    case 'LEAD_LEFT_UNASSIGNED':
      return { icon: UserX, tone: 'amber' };
    case 'INTAKE_REJECTED':
      return { icon: Ban, tone: 'rose' };
    default:
      return { icon: Repeat, tone: 'blue' };
  }
}

interface NotificationItemProps {
  notification: NotificationModel;
  onSelect: (notification: NotificationModel) => void;
}

export function NotificationItem({ notification, onSelect }: NotificationItemProps) {
  const { icon: Icon, tone } = iconFor(notification.kind);

  return (
    <li>
      <button
        onClick={() => onSelect(notification)}
        className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-800/50 ${
          notification.is_read ? '' : 'bg-slate-800/30'
        }`}
      >
        <span className={`p-1.5 rounded-lg border shrink-0 ${TONE_CLASSES[tone]}`}>
          <Icon className="w-4 h-4" aria-hidden="true" />
        </span>
        <span className="flex-1 min-w-0">
          <span className={`block text-sm ${notification.is_read ? 'text-slate-400' : 'text-slate-100 font-medium'}`}>
            {!notification.is_read && <span className="sr-only">Sin leer. </span>}
            {notification.message}
          </span>
          <span className="block text-xs text-slate-500 mt-0.5">{new Date(notification.created_at).toLocaleString()}</span>
        </span>
        {!notification.is_read && <span className="w-2 h-2 rounded-full bg-indigo-400 shrink-0 mt-1.5" aria-hidden="true" />}
      </button>
    </li>
  );
}
