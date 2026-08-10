import { useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { useSession } from '../../application/session/use-session';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';

interface LocationState {
  from?: { pathname: string };
  notice?: string;
}

export function LoginPage() {
  const { login } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const notice = (location.state as LocationState | null)?.notice;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      const from = (location.state as LocationState | null)?.from?.pathname;
      // '/' with no explicit origin defers to RootRedirect, which knows the role's panel.
      navigate(from ?? '/', { replace: true });
    } catch (err) {
      setError(readApiError(err)?.message ?? 'No se pudo iniciar sesión.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 p-8 border border-slate-800 rounded-xl bg-slate-900/40"
      >
        <h1 className="text-lg font-semibold">Iniciar sesión</h1>
        {notice && (
          <p className="text-sm bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg px-3 py-2">
            {notice}
          </p>
        )}
        <Field label="Correo">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="Contraseña" error={error ?? undefined}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <Button type="submit" submitting={submitting} submittingLabel="Entrando…" className="w-full">
          Entrar
        </Button>
      </form>
    </div>
  );
}
