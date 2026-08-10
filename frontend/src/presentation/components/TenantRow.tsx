import { useState } from 'react';
import type { Tenant, TenantUpdate } from '../../application/services/tenants.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';

interface TenantRowProps {
  tenant: Tenant;
  onUpdate: (id: string, body: TenantUpdate) => Promise<void>;
}

/** One organization: view mode with activate/deactivate, or an inline rename. The slug never shows as editable — it's derived once, at creation. */
export function TenantRow({ tenant, onUpdate }: TenantRowProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(tenant.name);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function runUpdate(body: TenantUpdate) {
    setSubmitting(true);
    setError(null);
    try {
      await onUpdate(tenant.id, body);
    } catch (err) {
      setError(readApiError(err)?.message ?? 'La acción no se pudo completar.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSave() {
    await runUpdate({ name });
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="p-4 space-y-3">
        <Field label="Nombre de la organización" error={error ?? undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setEditing(false)} disabled={submitting}>
            Cancelar
          </Button>
          <Button onClick={handleSave} submitting={submitting} submittingLabel="Guardando…">
            Guardar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 flex items-center justify-between gap-4">
      <div>
        <h4 className="font-semibold text-slate-200 text-sm">{tenant.name}</h4>
        <p className="text-xs text-slate-400 font-mono">
          {tenant.slug} • {tenant.agent_count ?? 0} asesores
        </p>
        {error && <p className="text-xs text-rose-400 mt-1">{error}</p>}
      </div>

      <div className="flex items-center gap-3">
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium border ${
            tenant.is_active
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
          }`}
        >
          {tenant.is_active ? 'Activa' : 'Inactiva'}
        </span>

        <Button variant="secondary" onClick={() => setEditing(true)} disabled={submitting}>
          Renombrar
        </Button>
        {tenant.is_active ? (
          <Button
            variant="danger"
            onClick={() => runUpdate({ is_active: false })}
            submitting={submitting}
            submittingLabel="Desactivando…"
          >
            Desactivar
          </Button>
        ) : (
          <Button onClick={() => runUpdate({ is_active: true })} submitting={submitting} submittingLabel="Activando…">
            Activar
          </Button>
        )}
      </div>
    </div>
  );
}
