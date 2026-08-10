import { describe, expect, it } from 'vitest';
import { evaluateAccess } from './role-guard';

describe('evaluateAccess', () => {
  it('neither redirects nor allows while the session is still loading', () => {
    expect(evaluateAccess('loading', undefined, ['AGENT'])).toBe('loading');
  });

  it('sends an anonymous session to the login screen', () => {
    expect(evaluateAccess('anonymous', undefined, ['AGENT'])).toBe('redirect-login');
  });

  it('denies a valid session with the wrong role instead of sending it to login', () => {
    expect(evaluateAccess('authenticated', 'AGENT', ['MANAGER'])).toBe('forbidden');
  });

  it('allows a session whose role is in the allow list', () => {
    expect(evaluateAccess('authenticated', 'MANAGER', ['MANAGER'])).toBe('allow');
  });
});
