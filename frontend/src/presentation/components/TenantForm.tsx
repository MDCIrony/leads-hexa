import { useState, type FormEvent } from 'react';
import { Building2 } from 'lucide-react';
import type { Tenant, TenantCreate } from '../../application/services/tenants.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from './ui/Button';
import { Field } from './ui/Field';
import { Input } from './ui/Input';

interface TenantFormProps {
  onCreate: (body: TenantCreate) => Promise<Tenant>;
}

const EMAIL_TAKEN_MESSAGE =
  'Ese correo ya está en uso en otra organización de la plataforma: la cuenta se identifica sólo por correo, no por organización.';

/**
 * The manager goes nested under `manager` in the same request — there is no
 * separate step to create it, so the form has to explain that the password
 * typed here belongs to someone else, who still needs to be told it.
 *
 * The success banner lives in the parent page, not here: `onCreate` triggers
 * a list refetch, which briefly flips the page into its loading state and
 * unmounts this form — any "created" state kept in it would vanish right
 * after the one moment it needs to be seen.
 */
export function TenantForm({ onCreate }: TenantFormProps) {
  const [name, setName] = useState('');
  const [managerName, setManagerName] = useState('');
  const [managerEmail, setManagerEmail] = useState('');
  const [managerPassword, setManagerPassword] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setNameError(null);
    setEmailError(null);
    try {
      await onCreate({
        name,
        manager: { name: managerName, email: managerEmail, password: managerPassword },
      });
      setName('');
      setManagerName('');
      setManagerEmail('');
      setManagerPassword('');
    } catch (err) {
      const apiError = readApiError(err);
      if (apiError?.error_code === 'TENANT_ALREADY_EXISTS') {
        setNameError(apiError.message);
      } else if (apiError?.error_code === 'EMAIL_ALREADY_EXISTS') {
        setEmailError(EMAIL_TAKEN_MESSAGE);
      } else {
        setNameError(apiError?.message ?? 'No se pudo crear la organización.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
      <h3 className="font-bold text-slate-100 flex items-center gap-2">
        <Building2 className="w-4 h-4 text-indigo-400" />
        Dar de alta una organización
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nombre de la organización" error={nameError ?? undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Nombre del gestor">
          <Input value={managerName} onChange={(e) => setManagerName(e.target.value)} required />
        </Field>
        <Field label="Correo del gestor" error={emailError ?? undefined}>
          <Input type="email" value={managerEmail} onChange={(e) => setManagerEmail(e.target.value)} required />
        </Field>
        <Field label="Contraseña del gestor">
          <Input
            type="password"
            value={managerPassword}
            onChange={(e) => setManagerPassword(e.target.value)}
            required
          />
        </Field>
      </div>

      <div className="flex justify-end">
        <Button type="submit" submitting={submitting} submittingLabel="Creando…">
          Crear organización
        </Button>
      </div>
    </form>
  );
}
