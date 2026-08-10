import { Navigate } from 'react-router';
import { useSession } from '../../application/session/use-session';

const PANEL_BY_ROLE: Record<string, string> = {
  ADMIN: '/admin/organizaciones',
  MANAGER: '/asesores',
  AGENT: '/mis-leads',
};

/** '/' has no view of its own: it only decides where the session's role lands. */
export function RootRedirect() {
  const { user, status } = useSession();

  if (status === 'loading') return null;
  if (status === 'anonymous') return <Navigate to="/login" replace />;

  return <Navigate to={(user && PANEL_BY_ROLE[user.role]) || '/login'} replace />;
}
