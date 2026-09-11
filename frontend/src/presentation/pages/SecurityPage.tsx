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
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function showError(error: unknown, fallback: string) {
    setError(readApiError(error)?.message ?? fallback);
  }

  async function setup(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await setupMfa(password);
      setSecret(result.secret);
      setUri(result.otpauth_uri);
    } catch (error) {
      showError(error, 'No se pudo iniciar la configuración.');
    } finally {
      setSubmitting(false);
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setCodes((await confirmMfa(code)).recovery_codes);
      setPassword('');
      setCode('');
      setSecret('');
      setUri('');
      await refresh();
    } catch (error) {
      showError(error, 'Código inválido.');
    } finally {
      setSubmitting(false);
    }
  }

  async function regenerate(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      setCodes((await regenerateMfa(password, code)).recovery_codes);
      setCode('');
    } catch (error) {
      showError(error, 'No se pudieron regenerar los códigos.');
    } finally {
      setSubmitting(false);
    }
  }

  async function disable() {
    if (!window.confirm('¿Desactivar la autenticación multifactor?')) return;
    setSubmitting(true);
    setError(null);
    try {
      await disableMfa(password, code);
      setPassword('');
      setCode('');
      setCodes([]);
      await refresh();
    } catch (error) {
      showError(error, 'No se pudo desactivar MFA.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">Seguridad</h1>
      <p className="text-slate-400">Autenticación multifactor: {user?.mfa_enabled ? 'activada' : 'desactivada'}.</p>
      {error && <p className="text-rose-400" role="alert">{error}</p>}

      {!user?.mfa_enabled && !secret && (
        <form onSubmit={setup} className="space-y-4">
          <Field label="Contraseña">
            <Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </Field>
          <Button type="submit" submitting={submitting} submittingLabel="Configurando…">Configurar MFA</Button>
        </form>
      )}

      {secret && (
        <form onSubmit={confirm} className="space-y-4">
          <QRCodeSVG value={uri} size={192} role="img" aria-label="Código QR para configurar MFA" />
          <p>Clave manual: <code className="break-all text-indigo-300">{secret}</code></p>
          <p className="text-sm text-slate-400">URI para importar en tu aplicación: <code className="break-all">{uri}</code></p>
          <Field label="Código de confirmación">
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
          <Field label="Contraseña">
            <Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </Field>
          <Field label="Código de autenticación o recuperación">
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
