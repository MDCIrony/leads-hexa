import { useState, type FormEvent } from 'react';
import { AssignmentStrategy, formatAssignmentStrategyLabel } from '../../domain/rule.model';
import type { Group, GroupCreate } from '../../application/services/groups.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';
import { Select } from './ui/Select';

interface GroupFormProps {
  /** Present when editing: the form starts from it and offers to cancel. */
  initial?: Group;
  submitLabel: string;
  onSubmit: (body: GroupCreate) => Promise<void>;
  onCancel?: () => void;
}

/** Create and edit share every field; SalesGroupCreate is also a valid SalesGroupUpdate. */
export function GroupForm({ initial, submitLabel, onSubmit, onCancel }: GroupFormProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [strategy, setStrategy] = useState(
    (initial?.default_strategy as AssignmentStrategy | undefined) ?? AssignmentStrategy.LOWEST_LOAD
  );
  // Kept as text: an empty box means "no cap", which the API reads as null.
  const [capacity, setCapacity] = useState(initial?.capacity_per_agent?.toString() ?? '');
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        name,
        description: description || null,
        default_strategy: strategy,
        capacity_per_agent: capacity === '' ? null : Number(capacity),
      });
      if (!initial) {
        setName('');
        setDescription('');
        setCapacity('');
      }
    } catch (err) {
      const apiError = readApiError(err);
      setError({ code: apiError?.error_code ?? '', message: apiError?.message ?? 'No se pudo guardar el grupo.' });
    } finally {
      setSubmitting(false);
    }
  }

  const capacityError = error?.code === 'INVALID_GROUP_CAPACITY' ? error.message : undefined;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nombre del grupo" error={capacityError ? undefined : error?.message}>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Descripción">
          <Input value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Estrategia por defecto">
          <Select value={strategy} onChange={(e) => setStrategy(e.target.value as AssignmentStrategy)}>
            {Object.values(AssignmentStrategy).map((s) => (
              <option key={s} value={s}>
                {formatAssignmentStrategyLabel(s)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Capacidad por asesor" error={capacityError}>
          <Input type="number" min={1} placeholder="Sin límite" value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </Field>
      </div>
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancelar
          </Button>
        )}
        <Button type="submit" submitting={submitting} submittingLabel="Guardando…">
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
