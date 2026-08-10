import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';
import { readApiError, translateApiError } from './api-error';

function axiosErrorWith(status: number, data: unknown): AxiosError {
  return new AxiosError('failed', String(status), undefined, undefined, {
    status,
    statusText: '',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
    data,
  });
}

describe('readApiError', () => {
  it('extracts the error_code from a 400 business error', () => {
    const error = axiosErrorWith(400, { error: true, error_code: 'RULE_WITHOUT_TARGET', message: 'x' });
    expect(readApiError(error)?.error_code).toBe('RULE_WITHOUT_TARGET');
  });

  it('returns null for anything that is not an axios error with the envelope shape', () => {
    expect(readApiError(new Error('boom'))).toBeNull();
  });
});

describe('translateApiError', () => {
  it('surfaces the field from a 422 validation failure', () => {
    const error = axiosErrorWith(422, {
      error: true,
      error_code: 'VALIDATION_ERROR',
      message: 'x',
      details: [{ field: 'budget', code: 'float_parsing', message: 'Input should be a valid number' }],
    });

    expect(translateApiError(error)).toEqual({
      kind: 'validation',
      details: [{ field: 'budget', code: 'float_parsing', message: 'Input should be a valid number' }],
    });
  });

  it('classifies a 401 as an expired session, not a business error', () => {
    expect(translateApiError(axiosErrorWith(401, {}))).toEqual({ kind: 'unauthorized' });
  });

  it('treats a 404 uniformly, matching ADR-0005: missing and cross-tenant look identical', () => {
    expect(translateApiError(axiosErrorWith(404, { error: true, error_code: 'LEAD_NOT_FOUND', message: 'x' }))).toEqual(
      { kind: 'not_found' }
    );
  });
});
