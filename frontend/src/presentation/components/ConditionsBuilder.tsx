import { Plus, Trash2 } from 'lucide-react';
import { Operator, type CriterionModel } from '../../domain/rule.model';
import { Input } from './ui/Input';

interface ConditionsBuilderProps {
  conditions: CriterionModel[];
  onChange: (conditions: CriterionModel[]) => void;
}

const OPERATORS = Object.values(Operator);
const VALUELESS_OPERATORS: Operator[] = [Operator.IS_EMPTY, Operator.IS_NOT_EMPTY];

function valueToInput(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ');
  return value === undefined || value === null ? '' : String(value);
}

function inputToValue(operator: Operator, raw: string): unknown {
  if (VALUELESS_OPERATORS.includes(operator)) return null;
  if (operator === Operator.IN) {
    return raw
      .split(',')
      .map((part) => part.trim())
      .filter((part) => part.length > 0);
  }
  return raw !== '' && !Number.isNaN(Number(raw)) ? Number(raw) : raw;
}

/**
 * Editor for a rule's conditions[] — ANDed within the rule (ADR-0011),
 * shared by scoring and assignment rules so a third family gets it for free.
 */
export function ConditionsBuilder({ conditions, onChange }: ConditionsBuilderProps) {
  function updateAt(index: number, patch: Partial<CriterionModel>) {
    onChange(conditions.map((c, i) => (i === index ? { ...c, ...patch } : c)));
  }

  function addCondition() {
    onChange([...conditions, { field: '', operator: Operator.EQUALS, value: '' }]);
  }

  function removeCondition(index: number) {
    onChange(conditions.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-slate-400">Condiciones (se cumplen todas)</label>
      {conditions.map((condition, index) => (
        <div key={index} className="grid grid-cols-1 md:grid-cols-[2fr_1.5fr_2fr_auto] gap-2 items-start">
          <Input
            placeholder="campo, ej. budget"
            value={condition.field}
            onChange={(e) => updateAt(index, { field: e.target.value })}
          />
          <select
            value={condition.operator}
            onChange={(e) => {
              const operator = e.target.value as Operator;
              updateAt(index, { operator, value: inputToValue(operator, valueToInput(condition.value)) });
            }}
            className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          >
            {OPERATORS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
          <Input
            placeholder={condition.operator === Operator.IN ? 'a, b, c' : 'valor'}
            value={valueToInput(condition.value)}
            disabled={VALUELESS_OPERATORS.includes(condition.operator)}
            onChange={(e) => updateAt(index, { value: inputToValue(condition.operator, e.target.value) })}
          />
          <button
            type="button"
            aria-label="Quitar condición"
            onClick={() => removeCondition(index)}
            className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addCondition}
        className="flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300"
      >
        <Plus className="w-3.5 h-3.5" />
        Añadir condición
      </button>
    </div>
  );
}
