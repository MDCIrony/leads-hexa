import { AlertTriangle } from 'lucide-react';
import { translateApiError } from '../../../infrastructure/api/api-error';
import { Button } from './Button';

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
}

/**
 * Every kind translateApiError can return, mapped to what the user reads.
 * `forbidden` and `business` already carry their own message from the
 * envelope; the rest are generic by design (401 redirects before this ever
 * renders, 404 must never hint that the record exists elsewhere).
 */
function describe(error: unknown): string {
  const action = translateApiError(error);
  switch (action.kind) {
    case 'unauthorized':
      return 'Tu sesión ha caducado.';
    case 'forbidden':
      return action.message;
    case 'not_found':
      return 'No existe.';
    case 'validation':
      return 'Hay datos inválidos en la petición.';
    case 'business':
      return action.message;
    case 'server':
      return 'Ha ocurrido un error en el servidor.';
    case 'unknown':
      return 'Ha ocurrido un error inesperado.';
  }
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-3 p-8 text-center">
      <AlertTriangle className="w-5 h-5 text-rose-400" aria-hidden="true" />
      <p className="text-slate-200">{describe(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </div>
  );
}
