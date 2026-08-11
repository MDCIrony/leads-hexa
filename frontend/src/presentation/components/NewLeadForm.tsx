import { useState, type FormEvent } from 'react';
import { Plus, Trash2, UserPlus } from 'lucide-react';
import type { IngestLeadRequest } from '../../application/services/intake.service';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import {
  buildCustomAttributes,
  validate,
  type AttributeRow,
  type FieldErrors,
} from './new-lead-validation';

interface NewLeadFormProps {
  submitting: boolean;
  onSubmit: (body: IngestLeadRequest) => Promise<void>;
}

export function NewLeadForm({ submitting, onSubmit }: NewLeadFormProps) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [company, setCompany] = useState('');
  const [industry, setIndustry] = useState('');
  const [budget, setBudget] = useState('');
  const [attributes, setAttributes] = useState<AttributeRow[]>([]);
  const [errors, setErrors] = useState<FieldErrors>({});

  function updateAttribute(index: number, patch: Partial<AttributeRow>) {
    setAttributes((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const fieldErrors = validate({ firstName, lastName, company, industry, budget });
    setErrors(fieldErrors);
    if (Object.keys(fieldErrors).length > 0) return;

    await onSubmit({
      first_name: firstName,
      last_name: lastName,
      email: email.trim() || undefined,
      phone: phone.trim() || undefined,
      company,
      budget: Number(budget),
      industry,
      custom_attributes: buildCustomAttributes(attributes),
    });

    // Cleared on success so a second submit cannot silently duplicate the lead
    // that was just ingested; the outcome card keeps the result on screen.
    setFirstName('');
    setLastName('');
    setEmail('');
    setPhone('');
    setCompany('');
    setIndustry('');
    setBudget('');
    setAttributes([]);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <h3 className="font-bold text-slate-100 flex items-center gap-2">
        <UserPlus className="w-4 h-4 text-indigo-400" />
        Nuevo lead
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nombre" error={errors.firstName}>
          <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </Field>
        <Field label="Apellidos" error={errors.lastName}>
          <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </Field>
        <Field label="Correo (opcional)">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Teléfono (opcional)">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field label="Empresa" error={errors.company}>
          <Input value={company} onChange={(e) => setCompany(e.target.value)} />
        </Field>
        <Field label="Sector" error={errors.industry}>
          <Input value={industry} onChange={(e) => setIndustry(e.target.value)} />
        </Field>
        <Field label="Presupuesto" error={errors.budget}>
          <Input value={budget} onChange={(e) => setBudget(e.target.value)} />
        </Field>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="block text-sm font-medium text-slate-200">Atributos personalizados (opcional)</span>
          <button
            type="button"
            onClick={() => setAttributes((rows) => [...rows, { key: '', value: '' }])}
            className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
          >
            <Plus className="w-3.5 h-3.5" />
            Añadir
          </button>
        </div>
        {attributes.map((row, index) => (
          <div key={index} className="flex items-center gap-2">
            <Input
              placeholder="clave"
              value={row.key}
              onChange={(e) => updateAttribute(index, { key: e.target.value })}
            />
            <Input
              placeholder="valor"
              value={row.value}
              onChange={(e) => updateAttribute(index, { value: e.target.value })}
            />
            <button
              type="button"
              aria-label="Quitar atributo"
              onClick={() => setAttributes((rows) => rows.filter((_, i) => i !== index))}
              className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Procesando…">
          Dar de alta
        </Button>
      </div>
    </form>
  );
}
