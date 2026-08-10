import { AgentModel } from '../../domain/agent.model';
import { AgentSettings } from '../components/AgentSettings';

interface SettingsPageProps {
  agents: AgentModel[];
  onAddAgent: (agent: Omit<AgentModel, 'id'>) => void;
}

export function SettingsPage({ agents, onAddAgent }: SettingsPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Configuración de Agentes y Webhooks</h2>
        <p className="text-sm text-slate-400">Gestiona la fuerza de ventas y las integraciones de notificación de eventos.</p>
      </div>

      <AgentSettings agents={agents} onAddAgent={onAddAgent} />
    </div>
  );
}
