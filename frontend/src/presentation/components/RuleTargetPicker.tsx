import type { AgentModel } from '../../domain/agent.model';
import type { Group } from '../../application/services/groups.service';
import { Field } from './ui/Field';
import { GroupSelect } from './GroupSelect';
import { TargetAgentsPicker } from './TargetAgentsPicker';

interface RuleTargetPickerProps {
  groups: Group[];
  agents: AgentModel[];
  groupId: string | null;
  agentIds: string[];
  onGroupChange: (groupId: string | null) => void;
  onAgentsChange: (agentIds: string[]) => void;
  /** false once the rule has a group: PATCH reads a null target_group_id as "unchanged", so it can't be removed. */
  allowNoGroup?: boolean;
}

/**
 * Where a rule sends its leads: a sales group, named agents, or both — with agent_match_mode ANY
 * the candidates are the union. Neither one is a 400 RULE_WITHOUT_TARGET, which the forms block first.
 */
export function RuleTargetPicker({ groups, agents, groupId, agentIds, onGroupChange, onAgentsChange, allowNoGroup = true }: RuleTargetPickerProps) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Grupo destino">
          <GroupSelect groups={groups} value={groupId} onChange={onGroupChange} allowNone={allowNoGroup} />
        </Field>
      </div>
      <p className="text-xs text-slate-400">
        Elige un grupo, asesores concretos o ambos: el lead va a cualquiera de ellos.
        {!allowNoGroup && ' El grupo de una regla se puede cambiar, pero no quitar.'}
      </p>
      <TargetAgentsPicker agents={agents} selected={agentIds} onChange={onAgentsChange} />
    </div>
  );
}
