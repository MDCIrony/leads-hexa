import { useEffect, useState, type FormEvent } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useSession } from '../../application/session/use-session';
import {
  confirmMfa, disableMfa, isOAuthProvider, oauthProviders, regenerateMfa, setupMfa,
  type OAuthProvider,
} from '../../application/services/auth.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';

export function SecurityPage() {
  const { user, refresh } = useSession();
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [uri, setUri] = useState('');
  const [codes, setCodes] = useState<string[]>([]);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [availableProviders, setAvailableProviders] = useState<OAuthProvider[] | null>(null);

  useEffect(() => {
    void oauthProviders()
      .then((result) => setAvailableProviders(result.providers.filter(isOAuthProvider)))
      .catch(() => setAvailableProviders([]));
  }, []);

  // The backend answers every wrong factor with the same generic envelope, so
  // the page names the field instead of echoing the English message.
  function factorError(error: unknown, fallback: string) {
    const envelope = readApiError(error);
    if (envelope?.error_code === 'INVALID_CREDENTIALS') return fallback;
    return envelope?.message ?? fallback;
  }

  async function setup(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setPasswordError(null);
    try {
      const result = await setupMfa(password);
      setSecret(result.secret);
      setUri(result.otpauth_uri);
    } catch (error) {
      setPasswordError(factorError(error, 'Contraseña incorrecta.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setCodeError(null);
    try {
      setCodes((await confirmMfa(code)).recovery_codes);
      setPassword('');
      setCode('');
      setSecret('');
      setUri('');
      await refresh();
    } catch (error) {
      setCodeError(factorError(error, 'Código inválido.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function regenerate(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setCodeError(null);
    try {
      setCodes((await regenerateMfa(password, code)).recovery_codes);
      setCode('');
    } catch (error) {
      setCodeError(factorError(error, 'Contraseña o código inválidos.'));
    } finally {
      setSubmitting(false);
    }
  }

  async function disable() {
    if (!window.confirm('¿Desactivar la autenticación multifactor?')) return;
    setSubmitting(true);
    setPasswordError(null);
    try {
      await disableMfa(password, code);
      setPassword('');
      setCode('');
      setCodes([]);
      await refresh();
    } catch (error) {
      setPasswordError(factorError(error, 'Contraseña o código inválidos.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold text-balance">Seguridad</h1>

      <section aria-labelledby="access-methods" className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <h2 id="access-methods" className="font-semibold text-balance">Métodos de acceso</h2>
        <p className="mt-1 text-sm text-slate-400 text-pretty">
          Consulta qué métodos protegen tu cuenta y cuáles están vinculados.
        </p>
        <dl className="mt-4 divide-y divide-slate-800">
          <div className="flex items-center justify-between gap-4 py-3">
            <dt>Autenticación multifactor</dt>
            <dd className={user?.mfa_enabled ? 'text-emerald-400' : 'text-slate-400'}>
              {user?.mfa_enabled ? 'Activada' : 'Desactivada'}
            </dd>
          </div>
          {(['GOOGLE', 'GITHUB'] as const).map((provider) => {
            const linked = user?.linked_oauth_providers?.includes(provider) ?? false;
            const available = availableProviders?.includes(provider) ?? false;
            const status = availableProviders === null
              ? 'Consultando…'
              : linked
                ? available ? 'Vinculado' : 'Vinculado, no disponible'
                : available ? 'Disponible, no vinculado' : 'No disponible';
            return (
              <div key={provider} className="flex items-center justify-between gap-4 py-3">
                <dt>{provider === 'GOOGLE' ? 'Google' : 'GitHub'}</dt>
                <dd className={linked && available ? 'text-emerald-400' : 'text-slate-400'}>{status}</dd>
              </div>
            );
          })}
        </dl>
      </section>

      {!user?.mfa_enabled && !secret && (
        <form onSubmit={setup} className="space-y-4">
          <Field label="Contraseña" error={passwordError ?? undefined}>
            <Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </Field>
          <Button type="submit" submitting={submitting} submittingLabel="Configurando…">Configurar MFA</Button>
        </form>
      )}

      {secret && (
        <form onSubmit={confirm} className="space-y-4">
          {/* The quiet zone is mandatory for scanners: without margin many readers never lock on. */}
          <QRCodeSVG value={uri} size={224} includeMargin role="img" aria-label="Código QR para configurar MFA" />
          <p>Clave manual: <code className="break-all text-indigo-300">{secret}</code></p>
          <p className="text-sm text-slate-400">URI para importar en tu aplicación: <code className="break-all">{uri}</code></p>
          <Field label="Código de confirmación" error={codeError ?? undefined}>
            <Input value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required autoFocus />
          </Field>
          <Button type="submit" submitting={submitting} submittingLabel="Confirmando…">Confirmar</Button>
        </form>
      )}

      {codes.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 p-4" aria-live="polite">
          <p className="mb-2">Guarda estos códigos; sólo se muestran ahora.</p>
          <code className="block whitespace-pre-wrap">{codes.join('\n')}</code>
        </div>
      )}

      {user?.mfa_enabled && (
        <form onSubmit={regenerate} className="space-y-4">
          <Field label="Contraseña" error={passwordError ?? undefined}>
            <Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </Field>
          <Field label="Código de autenticación o recuperación" error={codeError ?? undefined}>
            <Input value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required />
          </Field>
          <div className="flex gap-3">
            <Button type="submit" variant="secondary" submitting={submitting} submittingLabel="Regenerando…">Regenerar códigos</Button>
            <Button type="button" variant="danger" onClick={disable} disabled={submitting}>Desactivar MFA</Button>
          </div>
        </form>
      )}
    </div>
  );
}
