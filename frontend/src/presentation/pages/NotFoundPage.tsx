import { Link } from 'react-router';

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-2 bg-slate-950 text-slate-100">
      <h1 className="text-xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="text-indigo-400 hover:underline">
        Volver al inicio
      </Link>
    </div>
  );
}
