import { useState } from 'react';
import type { ScoringRuleModel } from '../../domain/rule.model';
import type { ScoringRuleUpdate } from '../../application/services/rules.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { ConditionsBuilder } from './ConditionsBuilder';

interface ScoringRuleRowProps {
  rule: ScoringRuleModel;
  onUpdate: (id: string, body: ScoringRuleUpdate) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

/** One scoring rule: view mode with toggle/delete, or a full inline edit of every field. */
export function ScoringRuleRow({ rule, onUpdate, onDelete }: ScoringRuleRowProps) {
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [name, setName] = useState(rule.name);
  const [conditions, setConditions] = useState(rule.conditions);
  const [scoreDelta, setScoreDelta] = useState(rule.scoreDelta);
  const [priority, setPriority] = useState(rule.priority);
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
    await runAction(() =>
      onUpdate(rule.id, {
        name,
        conditions: conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value })),
        score_delta: scoreDelta,
        priority,
      })
    );
    setEditing(false);
  }

  // Only is_active travels — sending the whole rule on a toggle is the bug
  // that wipes conditions[] a caller didn't mean to touch.
  const toggleActive = () => runAction(() => onUpdate(rule.id, { is_active: !rule.isActive }));

  if (editing) {
    return (
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Field label="Nombre" error={error ?? undefined}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Puntos que suma o resta">
            <Input type="number" value={scoreDelta} onChange={(e) => setScoreDelta(Number(e.target.value))} />
          </Field>
          <Field label="Prioridad">
            <Input type="number" value={priority} onChange={(e) => setPriority(Number(e.target.value))} />
          </Field>
        </div>
        <ConditionsBuilder conditions={conditions} onChange={setConditions} />
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
        <h4 className="font-semibold text-slate-200 text-sm">{rule.name}</h4>
        {rule.conditions.map((c, i) => (
          <p key={i} className="text-xs text-slate-400 font-mono mt-0.5">
            Si <span className="text-indigo-300">{c.field}</span> {c.operator}{' '}
            <span className="text-emerald-300">{String(c.value)}</span>
          </p>
        ))}
        <p className="text-xs text-slate-500 mt-0.5">Prioridad {rule.priority}</p>
        {error && <p className="text-xs text-rose-400 mt-1">{error}</p>}
      </div>

      <div className="flex items-center gap-3">
        <span className={`font-mono text-sm font-bold ${rule.scoreDelta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          {rule.scoreDelta >= 0 ? `+${rule.scoreDelta}` : rule.scoreDelta} pts
        </span>
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
            <span className="text-xs text-slate-400">Los leads ya puntuados conservan su desglose.</span>
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
