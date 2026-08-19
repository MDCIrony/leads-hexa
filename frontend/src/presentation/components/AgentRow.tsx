import { useState } from 'react';
import type { AgentModel } from '../../domain/agent.model';
import type { AgentUpdate } from '../../application/services/agents.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';

interface AgentRowProps {
  agent: AgentModel;
  onUpdate: (id: string, body: AgentUpdate) => Promise<void>;
  onDeactivate: (id: string) => Promise<void>;
  onReactivate: (id: string) => Promise<void>;
}

/** One advisor: view mode with status-aware actions, or an inline edit for the name. */
export function AgentRow({ agent, onUpdate, onDeactivate, onReactivate }: AgentRowProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(agent.name);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function runAction(action: () => Promise<void>) {
    setSubmitting(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(readApiError(err)?.message ?? 'La acción no se pudo completar.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSave() {
    await runAction(() => onUpdate(agent.id, { name }));
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Nombre completo" error={error ?? undefined}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setEditing(false)} disabled={submitting}>
            Cancelar
          </Button>
          <Button onClick={handleSave} submitting={submitting} submittingLabel="Guardando…">
            Guardar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 flex items-center justify-between gap-4">
      <div>
        <h4 className="font-semibold text-slate-200 text-sm">{agent.name}</h4>
        <p className="text-xs text-slate-400 font-mono">
          {agent.email} • <span className="text-indigo-400">{agent.role}</span>
        </p>
        {error && <p className="text-xs text-rose-400 mt-1">{error}</p>}
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium border ${
            agent.isActive
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
          }`}
        >
          {agent.isActive ? 'Activo' : 'Inactivo'}
        </span>

        {agent.isActive ? (
          <>
            <Button variant="secondary" onClick={() => setEditing(true)} disabled={submitting}>
              Editar
            </Button>
            <Button
              variant="danger"
              title="El asesor deja de poder entrar y de recibir leads nuevos; conserva los que ya tenía asignados."
              onClick={() => runAction(() => onDeactivate(agent.id))}
              submitting={submitting}
              submittingLabel="Desactivando…"
            >
              Desactivar
            </Button>
          </>
        ) : (
          <Button
            onClick={() => runAction(() => onReactivate(agent.id))}
            submitting={submitting}
            submittingLabel="Reactivando…"
          >
            Reactivar
          </Button>
        )}
      </div>
    </div>
  );
}
