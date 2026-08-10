import axios from 'axios';

export interface ApiErrorDetail {
  field: string;
  code: string;
  message: string;
}

/**
 * The backend's single error shape (docs/content/desarrollo/api-errores.md).
 * Not in schema.d.ts: the generated types describe FastAPI's default
 * per-route response, but a global exception handler rewrites every error
 * into this envelope at runtime — the generator never sees that rewrite.
 */
export interface ApiErrorEnvelope {
  error: true;
  error_code: string;
  message: string;
  details?: ApiErrorDetail[];
}

function isApiErrorEnvelope(data: unknown): data is ApiErrorEnvelope {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as Record<string, unknown>).error_code === 'string' &&
    typeof (data as Record<string, unknown>).message === 'string'
  );
}

/** Every page reads a failed request through this instead of destructuring the body itself. */
export function readApiError(error: unknown): ApiErrorEnvelope | null {
  if (!axios.isAxiosError(error) || !isApiErrorEnvelope(error.response?.data)) {
    return null;
  }
  return error.response!.data as ApiErrorEnvelope;
}

export type ApiErrorAction =
  | { kind: 'unauthorized' }
  | { kind: 'forbidden'; message: string }
  | { kind: 'not_found' }
  | { kind: 'validation'; details: ApiErrorDetail[] }
  | { kind: 'business'; errorCode: string; message: string }
  | { kind: 'server' }
  | { kind: 'unknown' };

/** The one place an HTTP status turns into what the UI does about it — see docs/content/desarrollo/api-errores.md. */
export function translateApiError(error: unknown): ApiErrorAction {
  const status = axios.isAxiosError(error) ? error.response?.status ?? null : null;
  const envelope = readApiError(error);

  switch (status) {
    case 401:
      // A session that expired is nobody's fault; the call site logs out and redirects.
      return { kind: 'unauthorized' };
    case 403:
      return { kind: 'forbidden', message: envelope?.message ?? 'No tienes acceso a esta acción.' };
    case 404:
      // Deliberately identical for "missing" and "belongs to another org" — see ADR-0005.
      return { kind: 'not_found' };
    case 422:
      return { kind: 'validation', details: envelope?.details ?? [] };
    case 400:
      if (envelope) return { kind: 'business', errorCode: envelope.error_code, message: envelope.message };
      return { kind: 'unknown' };
    default:
      if (status !== null && status >= 500) return { kind: 'server' };
      return { kind: 'unknown' };
  }
}
