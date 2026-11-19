import { useEffect, useState } from "react";
import { api } from "../api/client";

/** Images are access-controlled, so they are fetched with the bearer token and shown via a blob URL. */
export function SecureImage({ kind, id, alt }: { kind: "lost" | "found"; id: number; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null, cancelled = false;
    api.reportImage(kind, id).then(b => { if (!cancelled) { url = URL.createObjectURL(b); setSrc(url); } }).catch(() => {});
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [kind, id]);
  if (!src) return null;
  return <img src={src} alt={alt} style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 12 }} />;
}
