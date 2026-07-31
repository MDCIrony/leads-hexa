import { useState } from 'react';
import { AgentModel } from '../../domain/agent.model';
import { Users, UserPlus } from 'lucide-react';

interface AgentSettingsProps {
  agents: AgentModel[];
  onAddAgent: (agent: Omit<AgentModel, 'id' | 'activeLeadsCount'>) => void;
}

export function AgentSettings({ agents, onAddAgent }: AgentSettingsProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [team, setTeam] = useState('Enterprise');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;
    onAddAgent({ name, email, team, isActive: true });
    setName('');
    setEmail('');
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
        <h3 className="font-bold text-slate-100 flex items-center gap-2">
          <UserPlus className="w-4 h-4 text-indigo-400" />
          Registrar Agente de Ventas
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Nombre Completo</label>
            <input
              type="text"
              placeholder="Carlos Lopez"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Email</label>
            <input
              type="email"
              placeholder="clopez@sales.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Equipo / Especialización</label>
            <input
              type="text"
              placeholder="Enterprise / SMB"
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Guardar Agente
          </button>
        </div>
      </form>

      <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase flex items-center justify-between">
          <span>Agentes Registrados</span>
          <Users className="w-4 h-4 text-slate-500" />
        </div>
        <div className="divide-y divide-slate-800">
          {agents.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-sm">No hay agentes registrados.</div>
          ) : (
            agents.map((agent) => (
              <div key={agent.id} className="p-4 flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm">{agent.name}</h4>
                  <p className="text-xs text-slate-400 font-mono">{agent.email} • <span className="text-indigo-400">{agent.team}</span></p>
                </div>

                <div className="flex items-center gap-4">
                  <span className="text-xs font-mono bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-400">
                    Carga: {agent.activeLeadsCount} leads
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${agent.isActive ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                    {agent.isActive ? 'Activo' : 'Inactivo'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
