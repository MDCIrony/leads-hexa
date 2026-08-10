import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useAsync } from './use-async';

describe('useAsync', () => {
  it('starts loading and resolves with the data', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve('ok'), []));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBe('ok');
    expect(result.current.error).toBeNull();
  });

  it('surfaces a rejection as the error, not a thrown exception', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.reject(new Error('boom')), []));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBeNull();
    expect((result.current.error as Error).message).toBe('boom');
  });

  it('lets the newest request win over a slower, older one', async () => {
    // Deliberately resolves out of order: request 1 (offset 0) is slower
    // than request 2 (offset 1), the exact shape of a fast filter change.
    const responses: Record<number, { delay: number; value: string }> = {
      0: { delay: 30, value: 'stale' },
      1: { delay: 5, value: 'fresh' },
    };

    const { result, rerender } = renderHook(
      ({ offset }: { offset: number }) =>
        useAsync(() => {
          const { delay, value } = responses[offset];
          return new Promise<string>((resolve) => setTimeout(() => resolve(value), delay));
        }, [offset]),
      { initialProps: { offset: 0 } }
    );

    rerender({ offset: 1 });

    await waitFor(() => expect(result.current.data).toBe('fresh'));
    // Give the stale, slower response a chance to land — it must not overwrite it.
    await new Promise((resolve) => setTimeout(resolve, 40));
    expect(result.current.data).toBe('fresh');
  });

  it('refetch re-runs the same function', async () => {
    let calls = 0;
    const { result } = renderHook(() =>
      useAsync(() => {
        calls += 1;
        return Promise.resolve(calls);
      }, [])
    );

    await waitFor(() => expect(result.current.data).toBe(1));
    act(() => result.current.refetch());
    await waitFor(() => expect(result.current.data).toBe(2));
  });
});
