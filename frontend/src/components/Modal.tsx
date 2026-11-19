import { useEffect, type ReactNode } from "react";
import { Icon } from "./Icon";

export function Modal({ onClose, children, side = false, title }: {
  onClose: () => void; children: ReactNode; side?: boolean; title: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className={`overlay ${side ? "right" : "center"}`} onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={side ? "drawer" : "modal"} role="dialog" aria-modal="true" aria-label={title}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
