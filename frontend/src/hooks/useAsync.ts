import { useCallback, useEffect, useState } from 'react';
import { getApiError } from '../lib/utils';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Minimal async-data hook for one-shot fetches that fire on mount.
 *
 * Pass a **stable** function reference — a module-level API function, or one
 * wrapped in `useCallback` when the fetch depends on local state/props. The
 * hook treats a new function reference as a signal to re-fetch, so inline
 * arrow functions would cause an infinite loop; wrap them first.
 *
 * Returns `{ data, loading, error, reload }`. Call `reload()` after a
 * mutation to pull fresh data without a full page navigation.
 *
 * For polling or parametric queries, prefer TanStack Query (`useQuery` with
 * `refetchInterval` / `queryKey`).
 */
export function useAsync<T>(fn: () => Promise<T>): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // useCallback with empty deps keeps `run` stable across re-renders so the
  // useEffect below only fires once (and when reload() is explicitly called).
  // `fn` is intentionally omitted from deps — callers must pass stable refs.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(getApiError(err));
        setLoading(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    run();
  }, [run]);

  return { data, loading, error, reload: run };
}
