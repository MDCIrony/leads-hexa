import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  refetch: () => void;
}

/**
 * Runs `fn` whenever `deps` change and tracks loading/error/data for it.
 * Deliberately doesn't cache across components: nine views, two of them
 * lists, don't earn a shared cache — bring a library the day they do.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  // Guards two races at once: a response landing after the component
  // unmounted, and a stale request's response overwriting a newer one (the
  // classic bug when a filter changes faster than the network answers).
  const requestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    fn()
      .then((result) => {
        if (cancelled || id !== requestId.current) return;
        setData(result);
      })
      .catch((err: unknown) => {
        if (cancelled || id !== requestId.current) return;
        setError(err);
      })
      .finally(() => {
        if (cancelled || id !== requestId.current) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // `fn` is intentionally not a dependency: callers pass a fresh closure
    // each render, and `deps` is the explicit list of what should refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return { data, error, loading, refetch };
}
