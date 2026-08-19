import { Users } from 'lucide-react';
import type { AgentModel } from '../../domain/agent.model';
import type { AgentCreate, AgentUpdate } from '../../application/services/agents.service';
import { AgentForm } from './AgentForm';
import { AgentRow } from './AgentRow';

interface AgentSettingsProps {
  agents: AgentModel[];
  onCreate: (body: AgentCreate) => Promise<void>;
  onUpdate: (id: string, body: AgentUpdate) => Promise<void>;
  onDeactivate: (id: string) => Promise<void>;
  onReactivate: (id: string) => Promise<void>;
}

export function AgentSettings({ agents, onCreate, onUpdate, onDeactivate, onReactivate }: AgentSettingsProps) {
  return (
    <div className="space-y-6">
      <AgentForm onCreate={onCreate} />

      <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase flex items-center justify-between">
          <span>Asesores</span>
          <Users className="w-4 h-4 text-slate-500" />
        </div>
        <div className="divide-y divide-slate-800">
          {agents.map((agent) => (
            <AgentRow
              key={agent.id}
              agent={agent}
              onUpdate={onUpdate}
              onDeactivate={onDeactivate}
              onReactivate={onReactivate}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
