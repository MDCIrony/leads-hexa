// Mirrors the `allow` lists in app-routes.tsx as path prefixes, so a
// destination captured from a redirect can be checked against a role
// without pulling in the router.
const ROLE_PATH_PREFIXES: Record<string, readonly string[]> = {
  ADMIN: ['/admin', '/cuenta/seguridad'],
  MANAGER: ['/asesores', '/reglas', '/leads', '/cuenta/seguridad'],
  AGENT: ['/mis-leads', '/cuenta/seguridad'],
};

export interface PreviousDestination {
  pathname?: unknown;
  search?: unknown;
  hash?: unknown;
}

/** Whether `pathname` falls under one of `role`'s route prefixes. */
export function isPathAllowedForRole(role: string, pathname: string): boolean {
  const prefixes = ROLE_PATH_PREFIXES[role] ?? [];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/** Restores only a route the newly authenticated role can visit. */
export function allowedPreviousDestination(role: string, previous: PreviousDestination | undefined): string {
  if (!previous || typeof previous.pathname !== 'string' || !isPathAllowedForRole(role, previous.pathname)) {
    return '/';
  }
  const search = typeof previous.search === 'string' && previous.search.startsWith('?') ? previous.search : '';
  const hash = typeof previous.hash === 'string' && previous.hash.startsWith('#') ? previous.hash : '';
  return `${previous.pathname}${search}${hash}`;
}
