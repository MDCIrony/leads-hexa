import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import { setSessionExpiredListener } from '../../infrastructure/api/api-client';
import {
  login as loginRequest,
  logout as logoutRequest,
  rehydrateSession,
  type CurrentUser,
} from './session-service';

// Third state besides authenticated/anonymous: without it, a reload on a
// protected route flashes the login screen before the token is checked.
export type SessionStatus = 'loading' | 'authenticated' | 'anonymous';

export interface SessionContextValue {
  user: CurrentUser | null;
  status: SessionStatus;
  // Returns the freshly authenticated user: LoginPage needs the role to
  // decide whether a pending destination still applies.
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => void;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<SessionStatus>('loading');

  useEffect(() => {
    let cancelled = false;
    rehydrateSession().then((currentUser) => {
      if (cancelled) return;
      setUser(currentUser);
      setStatus(currentUser ? 'authenticated' : 'anonymous');
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const currentUser = await loginRequest(email, password);
    setUser(currentUser);
    setStatus('authenticated');
    return currentUser;
  }, []);

  // Navigating away on logout is the router's job; this only clears the
  // session state.
  const logout = useCallback(() => {
    logoutRequest();
    setUser(null);
    setStatus('anonymous');
  }, []);

  // A token that dies mid-session (expiry, revocation) is reported by
  // api-client as a 401 on some unrelated request; this is what turns that
  // into the same anonymous state a manual logout produces, so the guard
  // takes it from there instead of an error string painted in place.
  useEffect(() => {
    setSessionExpiredListener(logout);
    return () => setSessionExpiredListener(null);
  }, [logout]);

  return (
    <SessionContext.Provider value={{ user, status, login, logout }}>
      {children}
    </SessionContext.Provider>
  );
}
