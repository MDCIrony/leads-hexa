import { useState, type FormEvent } from 'react';
import { UserPlus } from 'lucide-react';
import type { AgentCreate } from '../../application/services/agents.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';

interface AgentFormProps {
  onCreate: (body: AgentCreate) => Promise<void>;
}

/**
 * Registers a new advisor — the API rejects a duplicate email with EMAIL_ALREADY_EXISTS.
 * A manager only ever mints advisors here, so the role is fixed instead of picked.
 * No group either: there is no groups view in this MVP to fill one.
 */
export function AgentForm({ onCreate }: AgentFormProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({ name, email, password, role: 'AGENT', is_active: true });
      setName('');
      setEmail('');
      setPassword('');
    } catch (err) {
      setError(readApiError(err)?.message ?? 'No se pudo registrar al asesor.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <h3 className="font-bold text-slate-100 flex items-center gap-2">
        <UserPlus className="w-4 h-4 text-indigo-400" />
        Registrar asesor
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nombre completo">
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Correo" error={error ?? undefined}>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Contraseña">
          <Input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
      </div>

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Guardando…">
          Guardar asesor
        </Button>
      </div>
    </form>
  );
}
