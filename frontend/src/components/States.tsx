import { useCallback, useEffect, useState, type ReactNode } from "react";

export const Loading = ({ label = "Loading…" }: { label?: string }) => (
  <div className="empty-state" role="status" aria-live="polite"><p>{label}</p></div>
);
export const ErrorBox = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div className="empty-state" role="alert">
    <h3>Something went wrong</h3><p>{message}</p>
    {onRetry && <button className="btn btn-light" onClick={onRetry}>Try again</button>}
  </div>
);
export const Empty = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className="empty-state"><div className="empty-symbol">⌕</div><h3>{title}</h3>{children}</div>
);

/** Fetch-on-mount hook returning loading/error/data and a reload function. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(() => {
    setLoading(true); setError(null);
    fn().then(setData).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return { data, error, loading, reload: run };
}
