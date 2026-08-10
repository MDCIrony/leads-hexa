import type { ReactNode } from 'react';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import type { LeadIntakeOutcome } from '../../application/data/use-lead-intake';

const TONE_CLASSES = {
  emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  rose: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
} as const;

function Card({ tone, icon, children }: { tone: keyof typeof TONE_CLASSES; icon: ReactNode; children: ReactNode }) {
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border ${TONE_CLASSES[tone]}`}>
      {icon}
      <div className="text-sm text-slate-200">{children}</div>
    </div>
  );
}

interface LeadOutcomeCardProps {
  outcome: LeadIntakeOutcome;
}

/**
 * Names one of the four ways a processed lead can land — a `202` alone never
 * says this, and an `UNASSIGNED` lead shown as generic success would read as
 * a broken routing engine instead of a rule nobody wrote yet.
 */
export function LeadOutcomeCard({ outcome }: LeadOutcomeCardProps) {
  switch (outcome.kind) {
    case 'assigned':
      return (
        <Card tone="emerald" icon={<CheckCircle2 className="w-5 h-5 shrink-0" aria-hidden="true" />}>
          Asignado a <span className="font-semibold">{outcome.agentName}</span> con{' '}
          <span className="font-mono font-semibold">{outcome.lead.score}</span> puntos.
        </Card>
      );
    case 'unassigned':
      return (
        <Card tone="amber" icon={<AlertTriangle className="w-5 h-5 shrink-0" aria-hidden="true" />}>
          Puntuación <span className="font-mono font-semibold">{outcome.lead.score}</span>. Ninguna regla de
          asignación lo recogió: quedó sin asignar.
        </Card>
      );
    case 'disqualified':
      return (
        <Card tone="rose" icon={<XCircle className="w-5 h-5 shrink-0" aria-hidden="true" />}>
          Descalificado: {outcome.lead.disqualificationReason ?? 'sin motivo registrado.'}
        </Card>
      );
    case 'rejected':
      return (
        <Card tone="rose" icon={<XCircle className="w-5 h-5 shrink-0" aria-hidden="true" />}>
          <p className="mb-1">Rechazado, y quedó en la bandeja para corregirlo:</p>
          <ul className="space-y-0.5">
            {outcome.errors.map((error, index) => (
              <li key={index}>
                <span className="font-mono">{error.field}:</span> <span>{error.message}</span>
              </li>
            ))}
          </ul>
        </Card>
      );
  }
}
