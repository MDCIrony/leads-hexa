import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react';
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
  login: (email: string, password: string) => Promise<void>;
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
  }, []);

  // Navigating away on logout is the router's job (next task); this only
  // clears the session and leaves the hole for it to fill.
  const logout = useCallback(() => {
    logoutRequest();
    setUser(null);
    setStatus('anonymous');
  }, []);

  return (
    <SessionContext.Provider value={{ user, status, login, logout }}>
      {children}
    </SessionContext.Provider>
  );
}
