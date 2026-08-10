import type { AppliedRuleModel } from '../../domain/lead.model';

interface LeadScoreBreakdownProps {
  score: number;
  breakdown: AppliedRuleModel[];
}

/**
 * Rule by rule, not just the total: the breakdown is what makes the score
 * explainable, and it's captured on the lead itself so it survives the
 * source rule being edited or deleted later.
 */
export function LeadScoreBreakdown({ score, breakdown }: LeadScoreBreakdownProps) {
  return (
    <div className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-100">Desglose de puntuación</h3>
        <span className="px-2 py-1 bg-indigo-500/10 text-indigo-400 rounded-md font-mono font-bold text-sm">
          {score} pts
        </span>
      </div>

      {breakdown.length === 0 ? (
        <p className="text-sm text-slate-500">Ninguna regla de puntuación aportó a este lead.</p>
      ) : (
        <ul className="divide-y divide-slate-800/50">
          {breakdown.map((rule) => (
            <li key={rule.ruleId} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-300">{rule.name}</span>
              <span className={rule.scoreDelta >= 0 ? 'text-emerald-400 font-mono' : 'text-rose-400 font-mono'}>
                {rule.scoreDelta >= 0 ? '+' : ''}
                {rule.scoreDelta}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
