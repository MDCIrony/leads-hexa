import { useLeadIntake } from '../../application/data/use-lead-intake';
import { NewLeadForm } from '../components/NewLeadForm';
import { LeadOutcomeCard } from '../components/LeadOutcomeCard';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';

export function NewLeadPage() {
  const { submitting, outcome, error, submit } = useLeadIntake();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Alta de lead</h2>
        <p className="text-sm text-slate-400">
          Da de alta un lead individual y sigue su procesamiento hasta el resultado final.
        </p>
      </div>

      <NewLeadForm submitting={submitting} onSubmit={submit} />

      {submitting && <LoadingState text="Procesando el lead…" />}
      {error ? <ErrorState error={error} /> : null}
      {outcome && <LeadOutcomeCard outcome={outcome} />}
    </div>
  );
}
