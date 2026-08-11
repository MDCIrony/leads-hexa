import { Layers, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router';
import { useSession } from '../../application/session/use-session';
import { NotificationBell } from './NotificationBell';

/** logout() only clears the session; navigating away is this call site's job. */
export function Header() {
  const { user, logout } = useSession();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/50 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
          <Layers className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-base font-bold text-slate-100 leading-tight">Lead Router</h1>
          <p className="text-xs text-slate-400">Plataforma Hexagonal Multi-tenant</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {user && (
          <div className="text-right text-xs">
            <p className="text-slate-200 font-medium">{user.name}</p>
            <p className="text-slate-500">{user.tenant_name ?? user.role}</p>
          </div>
        )}
        <NotificationBell />
        <button
          onClick={handleLogout}
          className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          title="Cerrar sesión"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
