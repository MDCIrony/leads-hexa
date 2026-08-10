// The backend issues the JWT in the response body and sets no cookie, so
// localStorage is the only place that survives a reload (decision in
// .plans/frontend/01-cimientos/README.md).
const TOKEN_KEY = 'leads-hexa:access_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
