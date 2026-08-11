import { useState } from 'react';
import { formatAssignmentStrategyLabel, type AssignmentRuleModel } from '../../domain/rule.model';
import type { AgentModel } from '../../domain/agent.model';
import type { AssignmentRuleUpdate } from '../../application/services/rules.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { AssignmentRuleEditForm } from './AssignmentRuleEditForm';

interface AssignmentRuleRowProps {
  rule: AssignmentRuleModel;
  agents: AgentModel[];
  onUpdate: (id: string, body: AssignmentRuleUpdate) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

/** One assignment rule: view mode with toggle/delete, or the full inline editor. */
export function AssignmentRuleRow({ rule, agents, onUpdate, onDelete }: AssignmentRuleRowProps) {
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
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

  async function handleSave(body: AssignmentRuleUpdate) {
    if (body.target_agent_ids && body.target_agent_ids.length === 0) {
      setError('Elige al menos un asesor destino.');
      return;
    }
    await runAction(() => onUpdate(rule.id, body));
    setEditing(false);
  }

  // Same partial-PATCH discipline as scoring rules: a toggle sends is_active alone.
  const toggleActive = () => runAction(() => onUpdate(rule.id, { is_active: !rule.isActive }));

  if (editing) {
    return (
      <AssignmentRuleEditForm
        rule={rule}
        agents={agents}
        error={error}
        submitting={submitting}
        onSave={handleSave}
        onCancel={() => setEditing(false)}
      />
    );
  }

  const targetNames = agents.filter((a) => rule.targetAgentIds.includes(a.id)).map((a) => a.name);

  return (
    <div className="p-4 flex items-center justify-between gap-4">
      <div>
        <h4 className="font-semibold text-slate-200 text-sm">{rule.name}</h4>
        <p className="text-xs text-slate-400 font-mono">
          {rule.minScore} – {rule.maxScore ?? '∞'} pts → {targetNames.join(', ') || 'sin asesores'}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          Prioridad {rule.priority} • {rule.strategy ? formatAssignmentStrategyLabel(rule.strategy) : 'sin estrategia'}
        </p>
        {error && <p className="text-xs text-rose-400 mt-1">{error}</p>}
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium border ${
            rule.isActive
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
          }`}
        >
          {rule.isActive ? 'Activa' : 'Inactiva'}
        </span>
        <Button variant="secondary" onClick={() => setEditing(true)} disabled={submitting}>
          Editar
        </Button>
        <Button variant="secondary" onClick={toggleActive} submitting={submitting} submittingLabel="Guardando…">
          {rule.isActive ? 'Desactivar' : 'Activar'}
        </Button>
        {confirmingDelete ? (
          <>
            <Button
              variant="danger"
              onClick={() => runAction(() => onDelete(rule.id))}
              submitting={submitting}
              submittingLabel="Borrando…"
            >
              Confirmar borrado
            </Button>
            <Button variant="secondary" onClick={() => setConfirmingDelete(false)} disabled={submitting}>
              Cancelar
            </Button>
          </>
        ) : (
          <Button variant="danger" onClick={() => setConfirmingDelete(true)} disabled={submitting}>
            Borrar
          </Button>
        )}
      </div>
    </div>
  );
}
