import { useState } from 'react';
import type { AssignmentRuleModel } from '../../domain/rule.model';
import type { AgentModel } from '../../domain/agent.model';
import type { Group } from '../../application/services/groups.service';
import type { AssignmentRuleUpdate } from '../../application/services/rules.service';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { ConditionsBuilder } from './ConditionsBuilder';
import { RuleTargetPicker } from './RuleTargetPicker';

interface AssignmentRuleEditFormProps {
  rule: AssignmentRuleModel;
  agents: AgentModel[];
  groups: Group[];
  error: string | null;
  submitting: boolean;
  onSave: (body: AssignmentRuleUpdate) => void;
  onCancel: () => void;
}

/** The inline edit for one assignment rule, preloaded with its current values. */
export function AssignmentRuleEditForm({ rule, agents, groups, error, submitting, onSave, onCancel }: AssignmentRuleEditFormProps) {
  const [name, setName] = useState(rule.name);
  const [minScore, setMinScore] = useState(rule.minScore);
  const [noMaxScore, setNoMaxScore] = useState(rule.maxScore === null);
  const [maxScore, setMaxScore] = useState(rule.maxScore ?? 0);
  const [targetGroupId, setTargetGroupId] = useState(rule.targetGroupId);
  const [targetAgentIds, setTargetAgentIds] = useState(rule.targetAgentIds);
  const [priority, setPriority] = useState(rule.priority);
  const [conditions, setConditions] = useState(rule.conditions);

  function handleSave() {
    onSave({
      name,
      min_score: minScore,
      max_score: noMaxScore ? null : maxScore,
      target_group_id: targetGroupId,
      target_agent_ids: targetAgentIds,
      priority,
      conditions: conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value })),
    });
  }

  return (
    <div className="p-4 space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Field label="Nombre" error={error ?? undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Puntuación mínima">
          <Input type="number" value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </Field>
        <div className="space-y-1">
          <label className="block text-sm font-medium text-slate-200">Puntuación máxima</label>
          <div className="flex items-center gap-2">
            <Input type="number" value={maxScore} disabled={noMaxScore} onChange={(e) => setMaxScore(Number(e.target.value))} />
            <label className="flex items-center gap-1.5 text-xs text-slate-400 whitespace-nowrap">
              <input type="checkbox" checked={noMaxScore} onChange={(e) => setNoMaxScore(e.target.checked)} />
              Sin techo
            </label>
          </div>
        </div>
      </div>
      <Field label="Prioridad">
        <Input type="number" value={priority} onChange={(e) => setPriority(Number(e.target.value))} />
      </Field>
      <RuleTargetPicker
        groups={groups}
        agents={agents}
        groupId={targetGroupId}
        agentIds={targetAgentIds}
        onGroupChange={setTargetGroupId}
        onAgentsChange={setTargetAgentIds}
        allowNoGroup={rule.targetGroupId === null}
      />
      <ConditionsBuilder conditions={conditions} onChange={setConditions} />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button onClick={handleSave} submitting={submitting} submittingLabel="Guardando…">
          Guardar
        </Button>
      </div>
    </div>
  );
}
