import { Inbox } from 'lucide-react';
import { Button } from './Button';

interface EmptyStateProps {
  text: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ text, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8 text-center">
      <Inbox className="w-5 h-5 text-slate-500" aria-hidden="true" />
      <p className="text-slate-400">{text}</p>
      {action && (
        <Button variant="secondary" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
