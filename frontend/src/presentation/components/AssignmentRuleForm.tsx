import { useState, type FormEvent } from 'react';
import { Target } from 'lucide-react';
import { AssignmentStrategy, formatAssignmentStrategyLabel, type CriterionModel } from '../../domain/rule.model';
import type { AgentModel } from '../../domain/agent.model';
import type { AssignmentRuleCreate } from '../../application/services/rules.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { ConditionsBuilder } from './ConditionsBuilder';
import { TargetAgentsPicker } from './TargetAgentsPicker';

interface AssignmentRuleFormProps {
  agents: AgentModel[];
  onCreate: (body: AssignmentRuleCreate) => Promise<void>;
}

/**
 * There's no groups view in this MVP, so the only reachable target is a set
 * of named agents — the form blocks an empty pick instead of letting the API
 * reject it with 400 RULE_WITHOUT_TARGET.
 */
export function AssignmentRuleForm({ agents, onCreate }: AssignmentRuleFormProps) {
  const [name, setName] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [noMaxScore, setNoMaxScore] = useState(true);
  const [maxScore, setMaxScore] = useState<number>(0);
  const [targetAgentIds, setTargetAgentIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<AssignmentStrategy>(AssignmentStrategy.ROUND_ROBIN);
  const [priority, setPriority] = useState(0);
  const [conditions, setConditions] = useState<CriterionModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (targetAgentIds.length === 0) {
      setError('Elige al menos un asesor destino.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        name,
        min_score: minScore,
        max_score: noMaxScore ? null : maxScore,
        target_agent_ids: targetAgentIds,
        agent_match_mode: 'ANY',
        strategy,
        priority,
        conditions: conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value })),
      });
      setName('');
      setMinScore(0);
      setNoMaxScore(true);
      setTargetAgentIds([]);
      setPriority(0);
      setConditions([]);
    } catch (err) {
      setError(readApiError(err)?.message ?? 'No se pudo crear la regla.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <h3 className="font-bold text-slate-100 flex items-center gap-2">
        <Target className="w-4 h-4 text-indigo-400" />
        Nueva regla de asignación
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Field label="Nombre" error={error ?? undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Puntuación mínima">
          <Input type="number" value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </Field>
        <div className="space-y-1">
          <label className="block text-sm font-medium text-slate-200">Puntuación máxima</label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={maxScore}
              disabled={noMaxScore}
              onChange={(e) => setMaxScore(Number(e.target.value))}
            />
            <label className="flex items-center gap-1.5 text-xs text-slate-400 whitespace-nowrap">
              <input type="checkbox" checked={noMaxScore} onChange={(e) => setNoMaxScore(e.target.checked)} />
              Sin techo
            </label>
          </div>
        </div>
        <Field label="Prioridad">
          <Input type="number" value={priority} onChange={(e) => setPriority(Number(e.target.value))} />
        </Field>
      </div>

      <div className="space-y-1">
        <label className="block text-sm font-medium text-slate-200">Estrategia de reparto</label>
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value as AssignmentStrategy)}
          className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
        >
          {Object.values(AssignmentStrategy).map((s) => (
            <option key={s} value={s}>
              {formatAssignmentStrategyLabel(s)}
            </option>
          ))}
        </select>
      </div>

      <TargetAgentsPicker agents={agents} selected={targetAgentIds} onChange={setTargetAgentIds} />

      <ConditionsBuilder conditions={conditions} onChange={setConditions} />

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Creando…">
          Crear regla
        </Button>
      </div>
    </form>
  );
}
