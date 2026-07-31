import { ScoringRuleModel } from '../../domain/rule.model';
import { RuleBuilderForm } from '../components/RuleBuilderForm';

interface RuleBuilderPageProps {
  rules: ScoringRuleModel[];
  onAddRule: (rule: Omit<ScoringRuleModel, 'id'>) => void;
  onDeleteRule: (id: string) => void;
}

export function RuleBuilderPage({ rules, onAddRule, onDeleteRule }: RuleBuilderPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Motor de Evaluación de Reglas</h2>
        <p className="text-sm text-slate-400">Configura criterios dinámicos para sumar o restar puntos a los leads ingestados.</p>
      </div>

      <RuleBuilderForm rules={rules} onAddRule={onAddRule} onDeleteRule={onDeleteRule} />
    </div>
  );
}
