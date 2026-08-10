import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  text?: string;
}

/** role="status" is what makes a spinner perceivable by a screen reader instead of silent motion. */
export function LoadingState({ text = 'Cargando…' }: LoadingStateProps) {
  return (
    <div role="status" className="flex flex-col items-center justify-center gap-3 p-8 text-slate-400">
      <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}
