import { useEffect, useState } from "react";
import { Icon } from "./Icon";

/** Images are access-controlled, so they are fetched with the bearer token and shown via a blob URL. */
export function SecureImage({ load, alt, className, deps = [], placeholder = true }: {
  load: (() => Promise<Blob>) | null; alt: string; className?: string; deps?: unknown[]; placeholder?: boolean;
}) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!load) { setSrc(null); return; }
    let url: string | null = null, cancelled = false;
    load().then(b => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } }).catch(() => {});
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  if (src) return <img src={src} alt={alt} className={className} />;
  return placeholder ? <div className={className ?? "thumb"} aria-label={`${alt} (no image)`}><Icon name="image" size={26} /></div> : null;
}
