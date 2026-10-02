import { useState } from 'react';
import { AssignmentStrategy, formatAssignmentStrategyLabel } from '../../domain/rule.model';
import type { Group, GroupUpdate } from '../../application/services/groups.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { GroupForm } from './GroupForm';
import { GroupMembers } from './GroupMembers';

interface GroupRowProps {
  group: Group;
  onUpdate: (id: string, body: GroupUpdate) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

/** One sales group: its summary and actions, the inline editor, or its members unfolded below. */
export function GroupRow({ group, onUpdate, onDelete }: GroupRowProps) {
  const [editing, setEditing] = useState(false);
  const [showMembers, setShowMembers] = useState(false);
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

  if (editing) {
    return (
      <div className="p-4">
        <GroupForm
          initial={group}
          submitLabel="Guardar"
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await onUpdate(group.id, body);
            setEditing(false);
          }}
        />
      </div>
    );
  }

  const strategy = formatAssignmentStrategyLabel(group.default_strategy as AssignmentStrategy);
  const capacity = group.capacity_per_agent ? `máx. ${group.capacity_per_agent} por asesor` : 'sin límite por asesor';

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h4 className="font-semibold text-slate-200 text-sm">{group.name}</h4>
          {group.description && <p className="text-xs text-slate-400">{group.description}</p>}
          <p className="text-xs text-slate-500 mt-0.5">
            {strategy} • {capacity} • {group.agent_count ?? 0} asesores
          </p>
          {error && <p className="text-xs text-rose-400 mt-1">{error}</p>}
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium border ${
              group.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
            }`}
          >
            {group.is_active ? 'Activo' : 'Inactivo'}
          </span>
          <Button variant="secondary" onClick={() => setShowMembers(!showMembers)} aria-expanded={showMembers}>
            {showMembers ? 'Ocultar miembros' : 'Ver miembros'}
          </Button>
          <Button variant="secondary" onClick={() => setEditing(true)} disabled={submitting}>
            Editar
          </Button>
          <Button
            variant="secondary"
            title="Un grupo inactivo deja de recibir asignaciones automáticas; sus asesores siguen con lo que tienen."
            onClick={() => runAction(() => onUpdate(group.id, { is_active: !group.is_active }))}
            submitting={submitting}
            submittingLabel="Guardando…"
          >
            {group.is_active ? 'Desactivar' : 'Activar'}
          </Button>
          {confirmingDelete ? (
            <>
              <Button variant="danger" onClick={() => runAction(() => onDelete(group.id))} submitting={submitting} submittingLabel="Borrando…">
                Confirmar borrado
              </Button>
              <Button variant="secondary" onClick={() => setConfirmingDelete(false)} disabled={submitting}>
                Cancelar
              </Button>
            </>
          ) : (
            <Button
              variant="danger"
              title="Sus asesores no se borran: quedan sin grupo."
              onClick={() => setConfirmingDelete(true)}
              disabled={submitting}
            >
              Borrar
            </Button>
          )}
        </div>
      </div>

      {showMembers && <GroupMembers groupId={group.id} />}
    </div>
  );
}
