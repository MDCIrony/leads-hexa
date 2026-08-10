import { Building2, LayoutDashboard, Sliders, UploadCloud, UserPlus, Users } from 'lucide-react';
import { NavLink } from 'react-router';
import { useSession } from '../../application/session/use-session';

interface MenuItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
}

// One entry per protected route in the routes table — see role-guard.tsx for the roles that gate them.
const MENU_BY_ROLE: Record<string, MenuItem[]> = {
  ADMIN: [{ to: '/admin/organizaciones', label: 'Organizaciones', icon: Building2 }],
  MANAGER: [
    { to: '/asesores', label: 'Asesores', icon: Users },
    { to: '/reglas/puntuacion', label: 'Reglas de puntuación', icon: Sliders },
    { to: '/reglas/asignacion', label: 'Reglas de asignación', icon: LayoutDashboard },
    { to: '/leads/nuevo', label: 'Alta de lead', icon: UserPlus },
    { to: '/leads/carga', label: 'Carga masiva', icon: UploadCloud },
  ],
  AGENT: [{ to: '/mis-leads', label: 'Mis leads', icon: LayoutDashboard }],
};

/** The menu comes from the session's role — never a locally-picked tab. */
export function Sidebar() {
  const { user } = useSession();
  const items = user ? (MENU_BY_ROLE[user.role] ?? []) : [];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/30 p-4 flex flex-col gap-2">
      <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
        Navegación
      </div>

      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`
          }
        >
          <Icon className="w-4 h-4" />
          <span>{label}</span>
        </NavLink>
      ))}
    </aside>
  );
}
