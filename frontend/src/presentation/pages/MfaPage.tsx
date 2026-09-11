import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { verifyMfa } from '../../application/services/auth.service';
import { useSession } from '../../application/session/use-session';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';
import { allowedPreviousDestination, type PreviousDestination } from '../routes/role-access';

export function MfaPage() {
  const { refresh } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setSubmitting(true); setError(null);
    try {
      await verifyMfa(code);
      const currentUser = await refresh();
      const from = (location.state as { from?: PreviousDestination } | null)?.from;
      navigate(currentUser ? allowedPreviousDestination(currentUser.role, from) : '/login', { replace: true });
    } catch (err) { setError(readApiError(err)?.message ?? 'No se pudo verificar el código.'); }
    finally { setSubmitting(false); }
  }
  return <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100"><form onSubmit={submit} className="w-full max-w-sm space-y-4 p-8 border border-slate-800 rounded-xl bg-slate-900/40"><h1 className="text-lg font-semibold">Verificación adicional</h1><p className="text-sm text-slate-400">Introduce el código de tu aplicación de autenticación o un código de recuperación.</p><Field label="Código" error={error ?? undefined}><Input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" required autoFocus /></Field><Button type="submit" submitting={submitting} submittingLabel="Verificando…" className="w-full">Verificar</Button></form></div>;
}
