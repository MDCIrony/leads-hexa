import { describe, expect, it } from 'vitest';
import { allowedPreviousDestination, isPathAllowedForRole } from './role-access';

describe('isPathAllowedForRole', () => {
  it('allows a role its own route', () => {
    expect(isPathAllowedForRole('MANAGER', '/asesores')).toBe(true);
  });

  it('allows a nested path under a role prefix', () => {
    expect(isPathAllowedForRole('AGENT', '/mis-leads/lead-1')).toBe(true);
  });

  it('denies a path that belongs to a different role', () => {
    expect(isPathAllowedForRole('AGENT', '/asesores')).toBe(false);
  });

  it('denies everything for an unknown role', () => {
    expect(isPathAllowedForRole('GHOST', '/asesores')).toBe(false);
  });

  it('restores query and fragment only for an allowed destination', () => {
    expect(allowedPreviousDestination('AGENT', { pathname: '/mis-leads', search: '?state=open', hash: '#table' })).toBe(
      '/mis-leads?state=open#table'
    );
    expect(allowedPreviousDestination('AGENT', { pathname: '/asesores' })).toBe('/');
  });
});
