import { useState, type FormEvent } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router';
import { create } from '../../application/services/agents.service';
import { readApiError } from '../../infrastructure/api/api-error';
import { Button } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';

const ALREADY_BOOTSTRAPPED_NOTICE = 'La plataforma ya tiene un administrador. Inicia sesión con tu cuenta.';

export function BootstrapPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // Role is required by the schema but ignored server-side: the first
      // agent always lands ADMIN, whatever this sends.
      await create({ name, email, password, role: 'ADMIN', is_active: true });
      navigate('/login', { replace: true });
    } catch (err) {
      // A 401 here isn't an expired session — nothing was ever logged in.
      // It means an admin already exists and bootstrap is closed, so it's
      // handled before readApiError/translateApiError ever see it: those
      // would read it as "your session expired".
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        navigate('/login', { replace: true, state: { notice: ALREADY_BOOTSTRAPPED_NOTICE } });
        return;
      }
      setError(readApiError(err)?.message ?? 'No se pudo crear el administrador.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 p-8 border border-slate-800 rounded-xl bg-slate-900/40"
      >
        <div>
          <h1 className="text-lg font-semibold">Arranque de la plataforma</h1>
          <p className="text-sm text-slate-400">Crea el primer administrador.</p>
        </div>
        <Field label="Nombre">
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Correo">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Contraseña" error={error ?? undefined}>
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </Field>
        <Button type="submit" submitting={submitting} submittingLabel="Creando…" className="w-full">
          Crear administrador
        </Button>
      </form>
    </div>
  );
}
