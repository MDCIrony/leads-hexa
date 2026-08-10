import { useState, type FormEvent } from 'react';
import { Sliders } from 'lucide-react';
import { Operator, type CriterionModel } from '../../domain/rule.model';
import type { ScoringRuleCreate } from '../../application/services/rules.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { ConditionsBuilder } from './ConditionsBuilder';

interface RuleBuilderFormProps {
  onCreate: (body: ScoringRuleCreate) => Promise<void>;
}

const EMPTY_CONDITIONS: CriterionModel[] = [{ field: '', operator: Operator.GREATER_THAN, value: '' }];

/** Creates a scoring rule — conditions[] is real, not a single flat field (ADR-0011). */
export function RuleBuilderForm({ onCreate }: RuleBuilderFormProps) {
  const [name, setName] = useState('');
  const [conditions, setConditions] = useState<CriterionModel[]>(EMPTY_CONDITIONS);
  const [scoreDelta, setScoreDelta] = useState<number>(25);
  const [priority, setPriority] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        name,
        conditions: conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value })),
        score_delta: scoreDelta,
        priority,
        is_active: true,
      });
      setName('');
      setConditions(EMPTY_CONDITIONS);
      setScoreDelta(25);
      setPriority(0);
    } catch (err) {
      setError(readApiError(err)?.message ?? 'No se pudo crear la regla.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <h3 className="font-bold text-slate-100 flex items-center gap-2">
        <Sliders className="w-4 h-4 text-indigo-400" />
        Nueva regla de puntuación
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Field label="Nombre" error={error ?? undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Puntos (score_delta)">
          <Input type="number" value={scoreDelta} onChange={(e) => setScoreDelta(Number(e.target.value))} />
        </Field>
        <Field label="Prioridad">
          <Input type="number" value={priority} onChange={(e) => setPriority(Number(e.target.value))} />
        </Field>
      </div>

      <ConditionsBuilder conditions={conditions} onChange={setConditions} />

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Creando…">
          Crear regla
        </Button>
      </div>
    </form>
  );
}
