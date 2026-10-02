import { Users } from 'lucide-react';
import type { AgentModel } from '../../domain/agent.model';
import type { AgentUpdate } from '../../application/services/agents.service';
import { AgentRow } from './AgentRow';

interface AgentSettingsProps {
  agents: AgentModel[];
  onUpdate: (id: string, body: AgentUpdate) => Promise<void>;
  onDeactivate: (id: string) => Promise<void>;
  onReactivate: (id: string) => Promise<void>;
}

/** The advisors list; the signup form lives outside it so an empty list still offers it. */
export function AgentSettings({ agents, ...rowActions }: AgentSettingsProps) {
  return (
    <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
      <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase flex items-center justify-between">
        <span>Asesores</span>
        <Users className="w-4 h-4 text-slate-500" />
      </div>
      <div className="divide-y divide-slate-800">
        {agents.map((agent) => (
          <AgentRow key={agent.id} agent={agent} {...rowActions} />
        ))}
      </div>
    </div>
  );
}
