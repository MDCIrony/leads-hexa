// Mirrors the `allow` lists in app-routes.tsx as path prefixes, so a
// destination captured from a redirect can be checked against a role
// without pulling in the router.
const ROLE_PATH_PREFIXES: Record<string, readonly string[]> = {
  ADMIN: ['/admin'],
  MANAGER: ['/asesores', '/reglas', '/leads'],
  AGENT: ['/mis-leads'],
};

/** Whether `pathname` falls under one of `role`'s route prefixes. */
export function isPathAllowedForRole(role: string, pathname: string): boolean {
  const prefixes = ROLE_PATH_PREFIXES[role] ?? [];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
