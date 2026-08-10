import { Link } from 'react-router';
import { Info } from 'lucide-react';
import { LeadModel, LeadStatus, formatLeadStatusLabel } from '../../domain/lead.model';

interface DashboardTableProps {
  leads: LeadModel[];
  /** Where the row's detail action points; the table has no opinion on which route owns lead detail. */
  getDetailHref: (lead: LeadModel) => string;
}

const STATUS_BADGE_STYLES: Record<LeadStatus, string> = {
  [LeadStatus.NEW]: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  [LeadStatus.QUALIFIED]: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  [LeadStatus.DISQUALIFIED]: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  [LeadStatus.UNASSIGNED]: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  [LeadStatus.ASSIGNED]: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  [LeadStatus.DISCARDED]: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
};

function StatusBadge({ status }: { status: LeadStatus }) {
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${STATUS_BADGE_STYLES[status]}`}>
      {formatLeadStatusLabel(status)}
    </span>
  );
}

/** Pure table render — filtering lives in the caller, which decides whether it's client or server side. */
export function DashboardTable({ leads, getDetailHref }: DashboardTableProps) {
  return (
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
          {leads.map((lead) => (
            <tr key={lead.id} className="hover:bg-slate-800/30 transition-colors">
              <td className="px-6 py-4">
                <div className="font-medium text-slate-100">{lead.firstName} {lead.lastName}</div>
                <div className="text-xs text-slate-400 font-mono">{lead.email}</div>
              </td>
              <td className="px-6 py-4">
                <div className="text-slate-200">{lead.company}</div>
                <div className="text-xs text-slate-500">{lead.industry}</div>
              </td>
              <td className="px-6 py-4 font-mono text-emerald-400">${lead.budget.toLocaleString()}</td>
              <td className="px-6 py-4">
                <span className="px-2 py-1 bg-indigo-500/10 text-indigo-400 rounded-md font-mono font-bold text-xs">
                  {lead.score} pts
                </span>
              </td>
              <td className="px-6 py-4">
                <StatusBadge status={lead.status} />
              </td>
              <td className="px-6 py-4 text-right">
                <Link
                  to={getDetailHref(lead)}
                  aria-label={`Ver detalle de ${lead.firstName} ${lead.lastName}`}
                  className="inline-block p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors"
                >
                  <Info className="w-4 h-4" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
