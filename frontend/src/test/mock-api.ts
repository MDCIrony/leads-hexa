import { vi } from 'vitest';
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios';
import { apiClient } from '../infrastructure/api/api-client';
import type { ApiErrorEnvelope } from '../infrastructure/api/api-error';

type HttpMethod = 'get' | 'post' | 'put' | 'patch' | 'delete';

/** One scripted response: a captured fixture, or the error envelope a status provokes. */
export type MockedRoute<T> = { status?: number; data: T } | { status: number; error: ApiErrorEnvelope };

function toAxiosResponse<T>(data: T, status: number): AxiosResponse<T> {
  return { data, status, statusText: '', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } };
}

function toAxiosError(status: number, error: ApiErrorEnvelope): AxiosError<ApiErrorEnvelope> {
  return new AxiosError(error.message, String(status), undefined, undefined, {
    status,
    statusText: '',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
    data: error,
  });
}

/**
 * Scripts apiClient.<method> by "METHOD path" instead of mocking axios's
 * internals, so a test states exactly the calls its view makes. A call to a
 * path the test didn't register rejects immediately instead of hanging.
 */
function makeHandler(method: HttpMethod, routes: Record<string, MockedRoute<unknown>>) {
  return (url: string): Promise<AxiosResponse<unknown>> => {
    const key = `${method.toUpperCase()} ${url}`;
    const route = routes[key];
    if (!route) {
      return Promise.reject(new Error(`mockApiClient: no route registered for ${key}`));
    }
    if ('error' in route) {
      return Promise.reject(toAxiosError(route.status, route.error));
    }
    return Promise.resolve(toAxiosResponse(route.data, route.status ?? 200));
  };
}

export function mockApiClient(routes: Record<string, MockedRoute<unknown>>): void {
  // Spied one literal method at a time — looping over a union of method
  // names makes vi.spyOn infer the combined overload type of all four and
  // reject any single-method implementation.
  vi.spyOn(apiClient, 'get').mockImplementation(makeHandler('get', routes) as unknown as typeof apiClient.get);
  vi.spyOn(apiClient, 'post').mockImplementation(makeHandler('post', routes) as unknown as typeof apiClient.post);
  vi.spyOn(apiClient, 'put').mockImplementation(makeHandler('put', routes) as unknown as typeof apiClient.put);
  vi.spyOn(apiClient, 'patch').mockImplementation(makeHandler('patch', routes) as unknown as typeof apiClient.patch);
  vi.spyOn(apiClient, 'delete').mockImplementation(
    makeHandler('delete', routes) as unknown as typeof apiClient.delete
  );
}
