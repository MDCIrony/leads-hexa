import { useState, type FormEvent } from 'react';
import { Target } from 'lucide-react';
import { AssignmentStrategy, formatAssignmentStrategyLabel, type CriterionModel } from '../../domain/rule.model';
import type { AgentModel } from '../../domain/agent.model';
import type { Group } from '../../application/services/groups.service';
import type { AssignmentRuleCreate } from '../../application/services/rules.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { Select } from './ui/Select';
import { ConditionsBuilder } from './ConditionsBuilder';
import { RuleTargetPicker } from './RuleTargetPicker';

interface AssignmentRuleFormProps {
  agents: AgentModel[];
  groups: Group[];
  onCreate: (body: AssignmentRuleCreate) => Promise<void>;
}

/** Blocks a rule with neither group nor agents instead of letting the API reject it with 400 RULE_WITHOUT_TARGET. */
export function AssignmentRuleForm({ agents, groups, onCreate }: AssignmentRuleFormProps) {
  const [name, setName] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [noMaxScore, setNoMaxScore] = useState(true);
  const [maxScore, setMaxScore] = useState<number>(0);
  const [targetGroupId, setTargetGroupId] = useState<string | null>(null);
  const [targetAgentIds, setTargetAgentIds] = useState<string[]>([]);
  const [strategy, setStrategy] = useState<AssignmentStrategy>(AssignmentStrategy.ROUND_ROBIN);
  const [priority, setPriority] = useState(0);
  const [conditions, setConditions] = useState<CriterionModel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!targetGroupId && targetAgentIds.length === 0) {
      setError('Elige un grupo o al menos un asesor destino.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        name,
        min_score: minScore,
        max_score: noMaxScore ? null : maxScore,
        target_group_id: targetGroupId,
        target_agent_ids: targetAgentIds,
        agent_match_mode: 'ANY',
        strategy,
        priority,
        conditions: conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value })),
      });
      setName('');
      setMinScore(0);
      setNoMaxScore(true);
      setTargetGroupId(null);
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

      <Field label="Estrategia de reparto">
        <Select value={strategy} onChange={(e) => setStrategy(e.target.value as AssignmentStrategy)}>
          {Object.values(AssignmentStrategy).map((s) => (
            <option key={s} value={s}>
              {formatAssignmentStrategyLabel(s)}
            </option>
          ))}
        </Select>
      </Field>

      <RuleTargetPicker
        groups={groups}
        agents={agents}
        groupId={targetGroupId}
        agentIds={targetAgentIds}
        onGroupChange={setTargetGroupId}
        onAgentsChange={setTargetAgentIds}
      />

      <ConditionsBuilder conditions={conditions} onChange={setConditions} />

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Creando…">
          Crear regla
        </Button>
      </div>
    </form>
  );
}
