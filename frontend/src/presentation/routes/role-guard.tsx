import { Navigate, Outlet, useLocation } from 'react-router';
import type { SessionStatus } from '../../application/session/session-context';
import { useSession } from '../../application/session/use-session';
import { Layout } from '../components/Layout';
import { ForbiddenPage } from '../pages/ForbiddenPage';

export type AccessDecision = 'loading' | 'redirect-login' | 'forbidden' | 'allow';

/**
 * Pure on purpose: the project has no render environment installed yet, so
 * this is the part of the guard that a test can cover without one.
 */
export function evaluateAccess(
  status: SessionStatus,
  role: string | undefined,
  allowedRoles: readonly string[]
): AccessDecision {
  if (status === 'loading') return 'loading';
  if (status === 'anonymous') return 'redirect-login';
  return role && allowedRoles.includes(role) ? 'allow' : 'forbidden';
}

interface RoleRouteProps {
  allow: readonly string[];
}

/** Gates a subtree of routes by role and wraps the granted ones in the app shell. */
export function RoleRoute({ allow }: RoleRouteProps) {
  const { user, status } = useSession();
  const location = useLocation();

  switch (evaluateAccess(status, user?.role, allow)) {
    case 'loading':
      // Neither login nor the page yet — this is what stops the flash on reload.
      return null;
    case 'redirect-login':
      return <Navigate to="/login" state={{ from: location }} replace />;
    case 'forbidden':
      // Never a silent redirect to login: a wrong role on a valid session must see why.
      return <ForbiddenPage />;
    default:
      return (
        <Layout>
          <Outlet />
        </Layout>
      );
  }
}
