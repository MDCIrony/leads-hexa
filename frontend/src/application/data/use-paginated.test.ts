import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { usePaginated, type PaginatedEnvelope } from './use-paginated';

function page(offset: number, total: number): PaginatedEnvelope<number> {
  const limit = 2;
  const items = Array.from({ length: Math.min(limit, Math.max(0, total - offset)) }, (_, i) => offset + i);
  return { items, total, limit, offset, has_more: offset + limit < total };
}

describe('usePaginated', () => {
  it('exposes the first page and total from the envelope', async () => {
    const fetchPage = vi.fn((_limit: number, offset: number) => Promise.resolve(page(offset, 5)));
    const { result } = renderHook(() => usePaginated(fetchPage, { limit: 2 }));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.items).toEqual([0, 1]);
    expect(result.current.total).toBe(5);
    expect(result.current.hasMore).toBe(true);
  });

  it('nextPage advances the offset it requests', async () => {
    const fetchPage = vi.fn((_limit: number, offset: number) => Promise.resolve(page(offset, 5)));
    const { result } = renderHook(() => usePaginated(fetchPage, { limit: 2 }));

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.nextPage());
    await waitFor(() => expect(result.current.items).toEqual([2, 3]));

    expect(fetchPage).toHaveBeenCalledWith(2, 2);
  });

  it('resets to page 0 when a dependency (a filter) changes', async () => {
    const fetchPage = vi.fn((_limit: number, offset: number) => Promise.resolve(page(offset, 5)));
    const { result, rerender } = renderHook(({ status }: { status: string }) => usePaginated(fetchPage, { limit: 2, deps: [status] }), {
      initialProps: { status: 'ALL' },
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.nextPage());
    await waitFor(() => expect(result.current.page).toBe(1));

    rerender({ status: 'ASSIGNED' });

    await waitFor(() => expect(result.current.page).toBe(0));
  });
});
