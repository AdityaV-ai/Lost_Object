import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Icon } from "./Icon";

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="empty" role="status" aria-live="polite"><p>{label}</p></div>
);
export const ErrorBox = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div className="empty" role="alert">
    <h3>Something went wrong</h3><p>{message}</p>
    {onRetry && <button className="btn" style={{ marginTop: 12 }} onClick={onRetry}>Try again</button>}
  </div>
);
export const Empty = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className="empty"><Icon name="search" size={28} /><h3>{title}</h3>{children}</div>
);

/** Fetch-on-mount hook returning loading/error/data and a reload function. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(() => {
    let live = true;
    setLoading(true); setError(null);
    fn().then(d => live && setData(d)).catch((e: Error) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return { data, error, loading, reload: run };
}

export function Async<T>({ q, children, empty }: {
  q: { data: T | null; error: string | null; loading: boolean; reload: () => void };
  children: (data: T) => ReactNode; empty?: (data: T) => ReactNode | null;
}) {
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorBox message={q.error} onRetry={q.reload} />;
  if (!q.data) return null;
  return <>{empty?.(q.data) ?? children(q.data)}</>;
}
