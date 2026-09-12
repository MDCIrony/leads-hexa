import { useState, type FormEvent } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useSession } from '../../application/session/use-session';
import { confirmMfa, disableMfa, regenerateMfa, setupMfa } from '../../application/services/auth.service';
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
      <h1 className="text-2xl font-semibold">Seguridad</h1>
      <p className="text-slate-400">Autenticación multifactor: {user?.mfa_enabled ? 'activada' : 'desactivada'}.</p>

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
