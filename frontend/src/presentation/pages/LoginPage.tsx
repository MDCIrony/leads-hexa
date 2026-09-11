import { useEffect, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router';
import {
  isMfaRequired, isOAuthProvider, oauthProviders, oauthStartUrl, type OAuthProvider,
} from '../../application/services/auth.service';
import { useSession } from '../../application/session/use-session';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';
import { allowedPreviousDestination, type PreviousDestination } from '../routes/role-access';

interface LocationState {
  from?: PreviousDestination;
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
  const [providers, setProviders] = useState<OAuthProvider[]>([]);
  const state = location.state as LocationState | null;
  const notice = state?.notice ?? (new URLSearchParams(location.search).get('oauth_error') === '1'
    ? 'No se pudo iniciar sesión con el proveedor.'
    : undefined);

  useEffect(() => {
    void oauthProviders().then((result) => setProviders(result.providers.filter(isOAuthProvider))).catch(() => setProviders([]));
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const currentUser = await login(email, password);
      if (isMfaRequired(currentUser)) {
        navigate('/mfa', { replace: true, state: { from: (location.state as LocationState | null)?.from } });
        return;
      }
      // A destination only survives login if the newly authenticated role can
      // reach it — otherwise it's someone else's leftover redirect (e.g. a
      // manager's session on /asesores expiring, then an agent logging in on
      // the same tab) and honoring it would drop the agent on a forbidden
      // page as their first sight of the app. '/' defers to RootRedirect,
      // which knows the role's own panel.
      const destination = allowedPreviousDestination(currentUser.role, (location.state as LocationState | null)?.from);
      navigate(destination, { replace: true });
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
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </Field>
        <Field label="Contraseña" error={error ?? undefined}>
          <Input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <Button type="submit" submitting={submitting} submittingLabel="Entrando…" className="w-full">
          Entrar
        </Button>
        {providers.map((provider) => (
          <a
            key={provider}
            href={oauthStartUrl(provider, typeof state?.from?.pathname === 'string' ? state.from.pathname : '/')}
            className="block w-full px-4 py-2 text-center rounded-lg font-medium border border-slate-800 text-slate-200 hover:bg-slate-800/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          >
            Continuar con {provider === 'GOOGLE' ? 'Google' : 'GitHub'}
          </a>
        ))}
      </form>
    </div>
  );
}
