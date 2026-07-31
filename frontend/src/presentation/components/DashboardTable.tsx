import { useState } from 'react';
import { LeadModel, LeadStatus, formatLeadStatusLabel } from '../../domain/lead.model';
import { Search, Filter, Info, X } from 'lucide-react';

interface DashboardTableProps {
  leads: LeadModel[];
}

export function DashboardTable({ leads }: DashboardTableProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedLead, setSelectedLead] = useState<LeadModel | null>(null);

  const filteredLeads = leads.filter((lead) => {
    const matchesSearch =
      lead.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      lead.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
      `${lead.firstName} ${lead.lastName}`.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'ALL' || lead.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: LeadStatus) => {
    const styles: Record<LeadStatus, string> = {
      [LeadStatus.NEW]: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      [LeadStatus.QUALIFIED]: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      [LeadStatus.DISQUALIFIED]: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      [LeadStatus.ASSIGNED]: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      [LeadStatus.FAILED]: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    };

    return (
      <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${styles[status]}`}>
        {formatLeadStatusLabel(status)}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-slate-900/40 p-4 rounded-xl border border-slate-800">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
          <input
            type="text"
            placeholder="Buscar por email, nombre o empresa..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
          >
            <option value="ALL">Todos los Estados</option>
            <option value={LeadStatus.NEW}>Nuevo</option>
            <option value={LeadStatus.QUALIFIED}>Calificado</option>
            <option value={LeadStatus.DISQUALIFIED}>Descalificado</option>
            <option value={LeadStatus.ASSIGNED}>Asignado</option>
            <option value={LeadStatus.FAILED}>Fallido</option>
          </select>
        </div>
      </div>

      <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-950 text-slate-400 text-xs uppercase border-b border-slate-800">
            <tr>
              <th className="px-6 py-3.5 font-semibold">Lead</th>
              <th className="px-6 py-3.5 font-semibold">Empresa / Industria</th>
              <th className="px-6 py-3.5 font-semibold">Presupuesto</th>
              <th className="px-6 py-3.5 font-semibold">Score</th>
              <th className="px-6 py-3.5 font-semibold">Estado</th>
              <th className="px-6 py-3.5 font-semibold text-right">Detalle</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {filteredLeads.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No se encontraron leads para el filtro seleccionado.
                </td>
              </tr>
            ) : (
              filteredLeads.map((lead) => (
                <tr key={lead.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-100">{lead.firstName} {lead.lastName}</div>
                    <div className="text-xs text-slate-400 font-mono">{lead.email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-slate-200">{lead.company}</div>
                    <div className="text-xs text-slate-500">{lead.industry}</div>
                  </td>
                  <td className="px-6 py-4 font-mono text-emerald-400">
                    ${lead.budget.toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-indigo-500/10 text-indigo-400 rounded-md font-mono font-bold text-xs">
                      {lead.score} pts
                    </span>
                  </td>
                  <td className="px-6 py-4">{getStatusBadge(lead.status)}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => setSelectedLead(lead)}
                      className="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors"
                      title="Ver desglose de reglas"
                    >
                      <Info className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedLead && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full space-y-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="font-bold text-lg text-slate-100">Desglose de Lead</h3>
              <button
                onClick={() => setSelectedLead(null)}
                className="text-slate-400 hover:text-slate-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-2 text-sm text-slate-300">
              <p><span className="text-slate-500">ID:</span> <span className="font-mono text-xs">{selectedLead.id}</span></p>
              <p><span className="text-slate-500">Nombre:</span> {selectedLead.firstName} {selectedLead.lastName}</p>
              <p><span className="text-slate-500">Email:</span> {selectedLead.email}</p>
              <p><span className="text-slate-500">Score Calculado:</span> <span className="font-bold text-indigo-400">{selectedLead.score} pts</span></p>
              <p><span className="text-slate-500">Estado Final:</span> {selectedLead.status}</p>
              <div className="pt-2">
                <span className="text-slate-500 text-xs font-semibold uppercase">Attributes:</span>
                <pre className="bg-slate-950 p-3 rounded-lg text-xs font-mono text-slate-400 mt-1 overflow-x-auto">
                  {JSON.stringify(selectedLead.customAttributes, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
