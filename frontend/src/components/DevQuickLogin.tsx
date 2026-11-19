// TEMPORARY test helper. Remove: delete this file, plus its import and <DevQuickLogin /> line in pages/AuthPages.tsx.
// Shown unless built with VITE_DEMO_LOGIN=0. Needs the demo accounts: the API creates them on startup (DEMO_ACCOUNTS=0 disables).
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errorText } from "../utils";

const DEMO = [
  { label: "Owner", email: "owner@demo.test", to: "/dashboard" },
  { label: "Finder", email: "finder@demo.test", to: "/dashboard" },
  { label: "Staff", email: "staff@demo.test", to: "/dashboard" },
];
const DEMO_PASSWORD = "Demo12345!";

export function DevQuickLogin({ onFill }: { onFill?: (email: string, password: string) => void }) {
  const { login } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  if (import.meta.env.VITE_DEMO_LOGIN === "0") return null;

  async function go(d: (typeof DEMO)[number]) {
    setBusy(d.label); setMsg(""); onFill?.(d.email, DEMO_PASSWORD);
    try { await login(d.email, DEMO_PASSWORD); nav(d.to, { replace: true }); }
    catch (err) { setMsg(errorText(err) + " If this is a fresh setup, restart the API once so it can create the demo accounts."); }
    finally { setBusy(""); }
  }
  return (
    <div style={{ marginTop: 18, paddingTop: 14, borderTop: "1px dashed var(--border, #888)" }}>
      <p className="muted" style={{ textAlign: "center", fontSize: 12, marginBottom: 8 }}>Test accounts: click to fill the form and sign in (password {DEMO_PASSWORD})</p>
      <div className="row" style={{ justifyContent: "center", gap: 8 }}>
        {DEMO.map(d => (
          <button key={d.label} type="button" className="btn" disabled={!!busy} onClick={() => go(d)}>
            {busy === d.label ? "…" : d.label}
          </button>
        ))}
      </div>
      {msg && <div className="msg error" role="alert" style={{ marginTop: 8 }}>{msg}</div>}
    </div>
  );
}
