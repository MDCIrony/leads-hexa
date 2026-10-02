import { useState, type FormEvent } from 'react';
import { UserPlus } from 'lucide-react';
import type { AgentCreate } from '../../application/services/agents.service';
import type { Group } from '../../application/services/groups.service';
import { GroupNotAssignedError } from '../../application/services/agent-roster.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { GroupSelect } from './GroupSelect';

interface AgentFormProps {
  groups: Group[];
  onCreate: (body: AgentCreate, groupId: string | null) => Promise<void>;
}

type FormError = { field: 'email' | 'group'; message: string };

/**
 * Registers a new advisor — the API rejects a duplicate email with EMAIL_ALREADY_EXISTS.
 * A manager only ever mints advisors here, so the role is fixed instead of picked.
 */
export function AgentForm({ groups, onCreate }: AgentFormProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [groupId, setGroupId] = useState<string | null>(null);
  const [error, setError] = useState<FormError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setName('');
    setEmail('');
    setPassword('');
    setGroupId(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({ name, email, password, role: 'AGENT', is_active: true }, groupId);
      reset();
    } catch (err) {
      if (err instanceof GroupNotAssignedError) {
        // The account exists: keeping the fields would only invite a resubmit that hits EMAIL_ALREADY_EXISTS.
        reset();
        const reason = readApiError(err.cause)?.message ?? 'inténtalo desde su fila.';
        setError({ field: 'group', message: `${err.agent.name} se registró sin grupo: ${reason}` });
      } else {
        setError({ field: 'email', message: readApiError(err)?.message ?? 'No se pudo registrar al asesor.' });
      }
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
        <Field label="Correo" error={error?.field === 'email' ? error.message : undefined}>
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
        <Field label="Grupo" error={error?.field === 'group' ? error.message : undefined}>
          <GroupSelect groups={groups} value={groupId} onChange={setGroupId} />
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
