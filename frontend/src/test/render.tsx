import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router';
import { SessionContext, type SessionContextValue } from '../application/session/session-context';
import type { CurrentUser } from '../application/session/session-service';
import meAdmin from './fixtures/me-admin.json';
import meManager from './fixtures/me-manager.json';
import meAgent from './fixtures/me-agent.json';

export type Role = 'ADMIN' | 'MANAGER' | 'AGENT';

// Captured GET /auth/me responses, one per role: what a view actually
// receives once logged in, not a role string invented for the test.
const USER_BY_ROLE: Record<Role, CurrentUser> = {
  ADMIN: meAdmin,
  MANAGER: meManager,
  AGENT: meAgent,
};

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Session role to render as. Omit to render anonymous. */
  role?: Role;
  /** Initial router location; defaults to the app root. */
  route?: string;
}

/**
 * Wraps a view with the router and a session context already resolved to
 * `role`, so a view test never has to drive the login form to get there.
 */
export function renderWithProviders(
  ui: ReactElement,
  { role, route = '/', ...options }: RenderWithProvidersOptions = {}
) {
  const user = role ? USER_BY_ROLE[role] : null;
  const session: SessionContextValue = {
    user,
    status: user ? 'authenticated' : 'anonymous',
    login: async () => {},
    logout: () => {},
  };

  return render(
    <MemoryRouter initialEntries={[route]}>
      <SessionContext.Provider value={session}>{ui}</SessionContext.Provider>
    </MemoryRouter>,
    options
  );
}
