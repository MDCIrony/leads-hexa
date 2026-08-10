import { useCallback, useEffect, useState } from 'react';
import { useAsync } from './use-async';

/** The one paginated envelope shape all sixteen list endpoints share. */
export interface PaginatedEnvelope<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface UsePaginatedResult<T> {
  items: T[];
  total: number;
  hasMore: boolean;
  loading: boolean;
  error: unknown;
  page: number;
  nextPage: () => void;
  previousPage: () => void;
  refetch: () => void;
}

interface UsePaginatedOptions {
  limit?: number;
  /** Filters or search terms; changing any of these resets to page 0. */
  deps?: readonly unknown[];
}

/** Wraps useAsync with the offset math every list view would otherwise repeat. */
export function usePaginated<T>(
  fetchPage: (limit: number, offset: number) => Promise<PaginatedEnvelope<T>>,
  { limit = 20, deps = [] }: UsePaginatedOptions = {}
): UsePaginatedResult<T> {
  const [page, setPage] = useState(0);

  // A filter changing while on page 3 must not keep querying offset 60 of a
  // now-different result set.
  useEffect(() => {
    setPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const offset = page * limit;
  const { data, error, loading, refetch } = useAsync(() => fetchPage(limit, offset), [limit, offset, ...deps]);

  const nextPage = useCallback(() => {
    if (data?.has_more) setPage((p) => p + 1);
  }, [data?.has_more]);

  const previousPage = useCallback(() => setPage((p) => Math.max(0, p - 1)), []);

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    hasMore: data?.has_more ?? false,
    loading,
    error,
    page,
    nextPage,
    previousPage,
    refetch,
  };
}
