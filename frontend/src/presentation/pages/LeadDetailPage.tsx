import { Link, useParams } from 'react-router';
import { ArrowLeft } from 'lucide-react';
import { useAsync } from '../../application/data/use-async';
import { get } from '../../application/services/leads.service';
import type { LeadModel } from '../../domain/lead.model';
import { AsyncView } from '../components/ui/AsyncView';
import { LeadScoreBreakdown } from '../components/LeadScoreBreakdown';

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500 uppercase">{label}</p>
      <p className="text-slate-200">{value}</p>
    </div>
  );
}

function LeadFacts({ lead }: { lead: LeadModel }) {
  const reason = lead.disqualificationReason ?? lead.discardReason;

  return (
    <div className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Fact label="Correo" value={lead.email ?? '—'} />
        <Fact label="Teléfono" value={lead.phone ?? '—'} />
        <Fact label="Empresa" value={lead.company} />
        <Fact label="Sector" value={lead.industry} />
        <Fact label="Presupuesto" value={`$${lead.budget.toLocaleString()}`} />
        <Fact label="Asignado el" value={lead.assignedAt ? new Date(lead.assignedAt).toLocaleString() : '—'} />
      </div>

      {reason && (
        <div className="bg-rose-500/10 border border-rose-500/20 rounded-lg p-3 text-sm text-rose-300">
          {reason}
        </div>
      )}

      {Object.keys(lead.customAttributes).length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase mb-1">Atributos personalizados</p>
          <pre className="bg-slate-950 p-3 rounded-lg text-xs font-mono text-slate-400 overflow-x-auto">
            {JSON.stringify(lead.customAttributes, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/** Read-only: the agent sees why they got this lead, never a way to reassign or discard it. */
export function LeadDetailPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const state = useAsync(() => get(leadId as string), [leadId]);

  return (
    <div className="space-y-6">
      <Link to="/mis-leads" className="inline-flex items-center gap-1 text-sm text-indigo-400 hover:underline">
        <ArrowLeft className="w-4 h-4" />
        Volver a mis leads
      </Link>

      <AsyncView state={state}>
        {(lead) => (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-slate-100">
                {lead.firstName} {lead.lastName}
              </h2>
              <p className="text-sm text-slate-400">{lead.company}</p>
            </div>

            <LeadFacts lead={lead} />
            <LeadScoreBreakdown score={lead.score} breakdown={lead.scoreBreakdown ?? []} />
          </div>
        )}
      </AsyncView>
    </div>
  );
}
