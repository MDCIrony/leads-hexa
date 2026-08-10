import { useState, type FormEvent } from 'react';
import { UserPlus } from 'lucide-react';
import type { AgentCreate } from '../../application/services/agents.service';
import type { Group } from '../../application/services/groups.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';

interface AgentFormProps {
  groups: Group[];
  onCreate: (body: AgentCreate) => Promise<void>;
}

const ROLES: AgentCreate['role'][] = ['AGENT', 'MANAGER', 'ADMIN'];

/** Registers a new advisor — the API rejects a duplicate email with EMAIL_ALREADY_EXISTS. */
export function AgentForm({ groups, onCreate }: AgentFormProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<AgentCreate['role']>('AGENT');
  const [groupId, setGroupId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({ name, email, password, role, is_active: true, group_id: groupId || null });
      setName('');
      setEmail('');
      setPassword('');
      setRole('AGENT');
      setGroupId('');
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
        <div className="space-y-1">
          <label htmlFor="agent-role" className="block text-sm font-medium text-slate-200">
            Rol
          </label>
          <select
            id="agent-role"
            value={role}
            onChange={(e) => setRole(e.target.value as AgentCreate['role'])}
            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label htmlFor="agent-group" className="block text-sm font-medium text-slate-200">
            Grupo (opcional)
          </label>
          <select
            id="agent-group"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            <option value="">Sin grupo</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Guardando…">
          Guardar asesor
        </Button>
      </div>
    </form>
  );
}
