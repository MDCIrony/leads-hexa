import type { AgentModel } from '../../domain/agent.model';

interface TargetAgentsPickerProps {
  agents: AgentModel[];
  selected: string[];
  onChange: (agentIds: string[]) => void;
}

/** The named agents of a rule's target; RuleTargetPicker puts the group next to it. */
export function TargetAgentsPicker({ agents, selected, onChange }: TargetAgentsPickerProps) {
  function toggle(agentId: string) {
    onChange(selected.includes(agentId) ? selected.filter((id) => id !== agentId) : [...selected, agentId]);
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-slate-200">Asesores destino</label>
      {agents.length === 0 ? (
        <p className="text-xs text-slate-500">No hay asesores activos a los que asignar.</p>
      ) : (
        <div className="flex flex-wrap gap-3 p-3 rounded-lg bg-slate-950 border border-slate-800">
          {agents.map((agent) => (
            <label key={agent.id} className="flex items-center gap-1.5 text-sm text-slate-200">
              <input type="checkbox" checked={selected.includes(agent.id)} onChange={() => toggle(agent.id)} />
              {agent.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
