import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

function Shell({ eyebrow, title, intro, note, children }: { eyebrow: string; title: React.ReactNode; intro: string; note: string; children: React.ReactNode }) {
  return (
    <div className="auth-page">
      <Link className="back-home" to="/">← Back to home</Link>
      <main className="auth-shell">
        <div className="auth-aside">
          <Link className="brand brand-light" to="/"><span className="brand-mark">F</span><span>FindBack<small>Campus Lost &amp; Found</small></span></Link>
          <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{intro}</p></div>
          <div className="aside-note">{note}</div>
        </div>
        <section className="auth-card">{children}</section>
      </main>
    </div>
  );
}

const fieldErrors = (e: unknown): string =>
  e instanceof ApiError && e.details.length ? e.details.map(d => d.message).join(" ") : (e as Error).message;

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/dashboard";
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setMsg("");
    try { await login(String(f.get("email")), String(f.get("password"))); nav(from, { replace: true }); }
    catch (err) { setMsg(fieldErrors(err)); }
    finally { setBusy(false); }
  }
  return (
    <Shell eyebrow="Welcome back" title={<>Good to see<br />you again.</>}
      intro="Sign in to manage your reports and review potential matches securely."
      note="Your reports and matching results are private to your account.">
      <span className="eyebrow">Your account</span><h2>Log in</h2>
      <p className="muted">Enter your registered email and password.</p>
      <form onSubmit={submit}>
        <label>Email address<input type="email" name="email" autoComplete="email" required placeholder="you@university.edu" /></label>
        <label>Password<input type="password" name="password" autoComplete="current-password" required placeholder="Your password" /></label>
        <div className="form-message error" role="status">{msg}</div>
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>{busy ? "Signing in…" : <>Log in <span>→</span></>}</button>
      </form>
      <p className="auth-switch">New to FindBack? <Link to="/register">Create an account</Link></p>
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
    if (f.get("password") !== f.get("confirm_password")) { setMsg("Passwords do not match."); return; }
    setBusy(true); setMsg("");
    try { await register(String(f.get("name")), String(f.get("email")), String(f.get("password"))); nav("/dashboard", { replace: true }); }
    catch (err) { setMsg(fieldErrors(err)); }
    finally { setBusy(false); }
  }
  return (
    <Shell eyebrow="A little peace of mind" title={<>Let's bring<br />things back<br />together.</>}
      intro="Create one account to report items you have lost or found." note="One account works for both owners and finders.">
      <span className="eyebrow">Get started</span><h2>Create account</h2>
      <p className="muted">A few details and you're ready to go.</p>
      <form onSubmit={submit}>
        <label>Full name<input name="name" required autoComplete="name" placeholder="Your full name" /></label>
        <label>Email address<input type="email" name="email" required autoComplete="email" placeholder="you@university.edu" /></label>
        <label>Password<input type="password" name="password" minLength={8} required autoComplete="new-password" placeholder="At least 8 characters" /></label>
        <label>Confirm password<input type="password" name="confirm_password" minLength={8} required autoComplete="new-password" placeholder="Re-enter password" /></label>
        <div className="form-message error" role="status">{msg}</div>
        <button className="btn btn-primary btn-block" type="submit" disabled={busy}>{busy ? "Creating account…" : <>Create account <span>→</span></>}</button>
      </form>
      <p className="auth-switch">Already registered? <Link to="/login">Log in</Link></p>
      <p className="tiny muted">Staff access is granted separately by the institution. You cannot select an admin role here.</p>
    </Shell>
  );
}
