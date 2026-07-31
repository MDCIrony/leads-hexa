import { LeadModel, LeadStatus } from '../../domain/lead.model';
import { DashboardTable } from '../components/DashboardTable';
import { Users, CheckCircle2, UserCheck, ShieldAlert } from 'lucide-react';

interface DashboardPageProps {
  leads: LeadModel[];
}

export function DashboardPage({ leads }: DashboardPageProps) {
  const totalLeads = leads.length;
  const qualifiedLeads = leads.filter((l) => l.status === LeadStatus.QUALIFIED || l.status === LeadStatus.ASSIGNED).length;
  const assignedLeads = leads.filter((l) => l.status === LeadStatus.ASSIGNED).length;
  const disqualifiedLeads = leads.filter((l) => l.status === LeadStatus.DISQUALIFIED).length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Dashboard de Leads</h2>
        <p className="text-sm text-slate-400">Resumen y monitoreo en tiempo real de prospectos ingestados.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase">Total Leads</p>
            <p className="text-2xl font-bold text-slate-100 mt-1 font-mono">{totalLeads}</p>
          </div>
          <div className="p-3 bg-blue-500/10 text-blue-400 rounded-lg border border-blue-500/20">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase">Calificados</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1 font-mono">{qualifiedLeads}</p>
          </div>
          <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase">Asignados</p>
            <p className="text-2xl font-bold text-purple-400 mt-1 font-mono">{assignedLeads}</p>
          </div>
          <div className="p-3 bg-purple-500/10 text-purple-400 rounded-lg border border-purple-500/20">
            <UserCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-slate-400 uppercase">Descalificados</p>
            <p className="text-2xl font-bold text-rose-400 mt-1 font-mono">{disqualifiedLeads}</p>
          </div>
          <div className="p-3 bg-rose-500/10 text-rose-400 rounded-lg border border-rose-500/20">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>
      </div>

      <DashboardTable leads={leads} />
    </div>
  );
}
