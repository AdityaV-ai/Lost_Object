import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { DevQuickLogin } from "../components/DevQuickLogin";
import { Icon } from "../components/Icon";
import { Logo, ThemeButton } from "../components/Layout";
import { errorText } from "../utils";

function Shell({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-top"><Logo /><div className="row"><Link className="btn btn-ghost" to="/">← Home</Link><ThemeButton /></div></div>
      <main className="card auth-card"><h1>{title}</h1><p className="muted" style={{ textAlign: "center", marginTop: 4 }}>{sub}</p>{children}</main>
    </div>
  );
}

function Password({ name, label, placeholder, auto }: { name: string; label: string; placeholder: string; auto: string }) {
  const [show, setShow] = useState(false);
  return (
    <label>{label}
      <div className="pw">
        <input type={show ? "text" : "password"} name={name} required minLength={name === "password" && auto === "new-password" ? 8 : undefined}
               autoComplete={auto} placeholder={placeholder} />
        <button type="button" onClick={() => setShow(s => !s)} aria-label={show ? "Hide password" : "Show password"}><Icon name="eye" size={16} /></button>
      </div>
    </label>
  );
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/dashboard";
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
  const fill = (email: string, password: string) => {
    const els = formRef.current?.elements as unknown as Record<string, HTMLInputElement> | undefined;
    if (els) { els.email.value = email; els.password.value = password; }
  };

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setMsg("");
    try { await login(String(f.get("email")), String(f.get("password"))); nav(from, { replace: true }); }
    catch (err) { setMsg(errorText(err)); }
    finally { setBusy(false); }
  }
  return (
    <Shell title="Log in to FindBack" sub="Manage your reports and review your private matches.">
      <form onSubmit={submit} ref={formRef}>
        <label>Email<input type="email" name="email" autoComplete="email" required placeholder="you@university.edu" /></label>
        <Password name="password" label="Password" placeholder="Your password" auto="current-password" />
        {msg && <div className="msg error" role="alert">{msg}</div>}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
      </form>
      <p className="muted" style={{ textAlign: "center", marginTop: 16 }}>New here? <Link to="/register">Create an account</Link></p>
      <DevQuickLogin onFill={fill} />
    </Shell>
  );
}

export function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get("password") !== f.get("confirm")) { setMsg("Passwords do not match."); return; }
    setBusy(true); setMsg("");
    try { await register(String(f.get("name")), String(f.get("email")), String(f.get("password"))); nav("/dashboard", { replace: true }); }
    catch (err) { setMsg(errorText(err)); }
    finally { setBusy(false); }
  }
  return (
    <Shell title="Create your account" sub="One account works for reporting lost and found items.">
      <form onSubmit={submit}>
        <label>Full name<input name="name" required autoComplete="name" placeholder="Your full name" /></label>
        <label>Email<input type="email" name="email" required autoComplete="email" placeholder="you@university.edu" /></label>
        <Password name="password" label="Password (8+ characters)" placeholder="At least 8 characters" auto="new-password" />
        <label>Confirm password<input type="password" name="confirm" required minLength={8} autoComplete="new-password" placeholder="Re-enter password" /></label>
        {msg && <div className="msg error" role="alert">{msg}</div>}
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="muted" style={{ textAlign: "center", marginTop: 16 }}>Already registered? <Link to="/login">Log in</Link></p>
      <p className="tiny muted" style={{ textAlign: "center", marginTop: 8 }}>Staff access is granted separately by the institution.</p>
    </Shell>
  );
}
