import { useState } from 'react';
import { ScoringRuleModel, Operator } from '../../domain/rule.model';
import { Plus, Trash2, Sliders } from 'lucide-react';

interface RuleBuilderFormProps {
  rules: ScoringRuleModel[];
  onAddRule: (rule: Omit<ScoringRuleModel, 'id'>) => void;
  onDeleteRule: (id: string) => void;
}

export function RuleBuilderForm({ rules, onAddRule, onDeleteRule }: RuleBuilderFormProps) {
  const [name, setName] = useState('');
  const [field, setField] = useState('budget');
  const [operator, setOperator] = useState<Operator>(Operator.GREATER_THAN);
  const [value, setValue] = useState('');
  const [scoreDelta, setScoreDelta] = useState<number>(25);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !field || !value) return;

    onAddRule({
      name,
      field,
      operator,
      value: isNaN(Number(value)) ? value : Number(value),
      scoreDelta,
    });

    setName('');
    setValue('');
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
        <h3 className="font-bold text-slate-100 flex items-center gap-2">
          <Sliders className="w-4 h-4 text-indigo-400" />
          Nueva Regla de Scoring
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">Nombre de Regla</label>
            <input
              type="text"
              placeholder="Ej: High Budget Lead"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Campo</label>
            <input
              type="text"
              placeholder="budget / industry"
              value={field}
              onChange={(e) => setField(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Operador</label>
            <select
              value={operator}
              onChange={(e) => setOperator(e.target.value as Operator)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value={Operator.EQUALS}>EQUALS</option>
              <option value={Operator.NOT_EQUALS}>NOT EQUALS</option>
              <option value={Operator.GREATER_THAN}>GREATER THAN</option>
              <option value={Operator.LESS_THAN}>LESS THAN</option>
              <option value={Operator.CONTAINS}>CONTAINS</option>
              <option value={Operator.IN}>IN</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Valor Comparar</label>
            <input
              type="text"
              placeholder="10000"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex justify-between items-center pt-2">
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-slate-400">Score Delta (+ / -):</label>
            <input
              type="number"
              value={scoreDelta}
              onChange={(e) => setScoreDelta(Number(e.target.value))}
              className="w-24 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-indigo-400 font-bold focus:outline-none focus:border-indigo-500"
            />
          </div>

          <button
            type="submit"
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Agregar Regla
          </button>
        </div>
      </form>

      <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase">
          Reglas Activas
        </div>
        <div className="divide-y divide-slate-800">
          {rules.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-sm">No hay reglas configuradas.</div>
          ) : (
            rules.map((rule) => (
              <div key={rule.id} className="p-4 flex items-center justify-between hover:bg-slate-800/20">
                <div>
                  <h4 className="font-semibold text-slate-200 text-sm">{rule.name}</h4>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    If <span className="text-indigo-300">{rule.field}</span> {rule.operator} <span className="text-emerald-300">{String(rule.value)}</span>
                  </p>
                </div>

                <div className="flex items-center gap-4">
                  <span className={`font-mono text-sm font-bold ${rule.scoreDelta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {rule.scoreDelta >= 0 ? `+${rule.scoreDelta}` : rule.scoreDelta} pts
                  </span>
                  <button
                    onClick={() => onDeleteRule(rule.id)}
                    className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
