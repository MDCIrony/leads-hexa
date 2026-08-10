import { Link } from 'react-router';

/** What a valid session with the wrong role sees — never a redirect to login, which would read as a bad password. */
export function ForbiddenPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-2 bg-slate-950 text-slate-100">
      <h1 className="text-xl font-semibold">No tienes acceso</h1>
      <p className="text-slate-400">Tu cuenta no tiene el rol necesario para ver esta pantalla.</p>
      <Link to="/" className="text-indigo-400 hover:underline">
        Volver al inicio
      </Link>
    </div>
  );
}
