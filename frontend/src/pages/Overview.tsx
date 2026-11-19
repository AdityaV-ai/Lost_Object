import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Claim, Match, Notification, Report } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icon";
import { useUnread } from "../components/Layout";
import { Modal } from "../components/Modal";
import { SecureImage } from "../components/SecureImage";
import { Async, Empty, useAsync } from "../components/States";
import { Stepper } from "../components/Widgets";
import { CATEGORIES, CUSTODY_TEXT, errorText, fmtDateTime, statusChip } from "../utils";

type Tab = "lost" | "found" | "recovery" | "notifications";
const TABS: [Tab, string][] = [["lost", "My lost reports"], ["found", "My found reports"],
  ["recovery", "Recovery requests"], ["notifications", "Notifications"]];

const Chip = ({ status }: { status: string }) => { const c = statusChip(status); return <span className={`chip ${c.cls}`}><span className="dot" />{c.text}</span>; };

function EditModal({ kind, report, onClose, onSaved }: { kind: "lost" | "found"; report: Report; onClose: () => void; onSaved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget).entries()) as Record<string, string>;
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(f)) body[k] = v.trim() === "" ? null : v.trim();
    if (!body.item_name) delete body.item_name;
    setBusy(true); setMsg("");
    try { await api.editReport(kind, report.id, body); onSaved(); onClose(); }
    catch (err) { setMsg(errorText(err)); setBusy(false); }
  }
  return (
    <Modal title={`Edit ${report.report_code}`} onClose={onClose}>
      <p className="muted tiny">Changing details re-scores your existing matches. The photo cannot be changed; file a new report for a different photo.</p>
      <form onSubmit={submit} className="grid2" style={{ marginTop: 12 }}>
        <label className="full">Item name<input name="item_name" defaultValue={report.item_name === "Unidentified item" ? "" : report.item_name} /></label>
        <label>Category<select name="category" defaultValue={report.category}>
          {[...new Set([report.category, ...CATEGORIES])].map(c => <option key={c}>{c}</option>)}</select></label>
        <label>Colour<input name="colour" defaultValue={report.colour ?? ""} /></label>
        {kind === "lost" && <><label>Brand<input name="brand" defaultValue={report.brand ?? ""} /></label>
          <label>Model<input name="model" defaultValue={report.model ?? ""} /></label></>}
        <label className="full">Distinguishing features<textarea name="distinguishing_features" defaultValue={report.distinguishing_features ?? ""} /></label>
        <label className="full">Description<textarea name="description" defaultValue={report.description ?? ""} /></label>
        {msg && <div className="msg error full" role="alert">{msg}</div>}
        <div className="row full" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button></div>
      </form>
    </Modal>
  );
}

function LostCard({ r, reload }: { r: Report; reload: () => void }) {
  const [edit, setEdit] = useState(false);
  const [err, setErr] = useState("");
  const active = r.status === "ACTIVE";
  async function resolve() {
    if (!window.confirm("Mark this item as found by you? Your report will be closed and any open claim withdrawn.")) return;
    try { await api.resolveLost(r.id); reload(); } catch (e) { setErr(errorText(e)); }
  }
  return (
    <article className="card report">
      <div className="report-top">
        <SecureImage load={r.has_image ? () => api.reportImage("lost", r.id) : null} alt={r.item_name} className="thumb" deps={[r.id]} />
        <div className="report-body">
          <h3>{r.item_name} <span className="mono muted tiny">{r.report_code}</span></h3>
          <p className="desc">{r.description ?? r.category}</p>
          <div className="row">
            <Chip status={r.status} />
            {r.match_count > 0 && <span className="chip blue">{r.match_count} potential match{r.match_count > 1 ? "es" : ""}</span>}
            {r.location && <span className="muted tiny"><Icon name="pin" size={13} /> {r.location}</span>}
            <span className="muted tiny">{fmtDateTime(r.occurred_at ?? r.created_at)}</span>
          </div>
          {err && <div className="msg error" role="alert">{err}</div>}
        </div>
        <div className="report-actions">
          {r.match_count > 0 && <Link className="btn btn-primary btn-sm" to={`/matches?lost=${r.id}`}>View matches</Link>}
          {active && <button className="btn btn-sm" onClick={() => setEdit(true)}><Icon name="edit" size={14} />Edit</button>}
          {active && <button className="btn btn-ghost btn-sm" onClick={() => void resolve()}>Found it myself</button>}
        </div>
      </div>
      {r.timeline && r.status !== "RESOLVED" && <Stepper t={r.timeline} />}
      {edit && <EditModal kind="lost" report={r} onClose={() => setEdit(false)} onSaved={reload} />}
    </article>
  );
}

function FoundCard({ r, reload }: { r: Report; reload: () => void }) {
  const [edit, setEdit] = useState(false);
  return (
    <article className="card report">
      <div className="report-top">
        <SecureImage load={r.has_image ? () => api.reportImage("found", r.id) : null} alt={r.item_name} className="thumb" deps={[r.id]} />
        <div className="report-body">
          <h3>{r.item_name} <span className="mono muted tiny">{r.report_code}</span></h3>
          <p className="desc">{r.description ?? r.category}</p>
          <div className="row">
            <Chip status={r.status} />
            <span className="chip">{CUSTODY_TEXT[r.custody_status ?? ""] ?? r.custody_status}</span>
            {r.match_count > 0 && <span className="chip blue">{r.match_count} possible owner{r.match_count > 1 ? "s" : ""}</span>}
            {r.location && <span className="muted tiny"><Icon name="pin" size={13} /> {r.location}</span>}
            <span className="muted tiny">{fmtDateTime(r.occurred_at ?? r.created_at)}</span>
          </div>
        </div>
        <div className="report-actions">
          {r.status === "ACTIVE" && <button className="btn btn-sm" onClick={() => setEdit(true)}><Icon name="edit" size={14} />Edit</button>}
        </div>
      </div>
      {edit && <EditModal kind="found" report={r} onClose={() => setEdit(false)} onSaved={reload} />}
    </article>
  );
}

function Recovery({ claims, matches, reload }: { claims: Claim[]; matches: Match[]; reload: () => void }) {
  const byMatch = new Map(matches.map(m => [m.id, m]));
  if (!claims.length) return <Empty title="No recovery requests yet.">
    <p>Press “Might be mine” on a match to start one. Staff will check your details.</p></Empty>;
  return <>{claims.map(c => {
    const m = byMatch.get(c.match_id);
    return (
      <div className="card item" key={c.id}>
        <div className="grow"><strong>{m ? `${m.lost_report.item_name} (${m.lost_report.report_code})` : `Match #${c.match_id}`}</strong>
          <div className="row" style={{ marginTop: 4 }}><Chip status={c.status} /><span className="muted tiny">Requested {fmtDateTime(c.created_at)}</span></div>
          {c.proof && <p className="muted tiny" style={{ marginTop: 6 }}>Your details: “{c.proof}”</p>}
        </div>
        <Link className="btn btn-sm" to={`/matches?match=${c.match_id}`}>View match</Link>
        {(c.status === "PENDING" || c.status === "VERIFIED") &&
          <button className="btn btn-sm btn-danger" onClick={() => void api.cancelClaim(c.id).then(reload)}>Cancel</button>}
      </div>);
  })}</>;
}

function Notes({ items, reload }: { items: Notification[]; reload: () => void }) {
  const nav = useNavigate();
  const unread = useUnread();
  const unreadN = items.filter(n => !n.is_read).length;
  if (!items.length) return <Empty title="No notifications yet.">
    <p>You will be told here when a found item looks like one of yours.</p></Empty>;
  const done = () => { reload(); unread.refresh(); };
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <span className="muted">{unreadN} unread</span>
        {unreadN > 0 && <button className="btn btn-sm" onClick={() => void api.readAll().then(done)}><Icon name="check" size={14} />Mark all read</button>}
      </div>
      {items.map(n => (
        <div className={`card item${n.is_read ? "" : " unread"}`} key={n.id}>
          <div className="grow"><strong>{n.title}</strong><p className="muted">{n.message}</p>
            <span className="muted tiny">{fmtDateTime(n.created_at)}</span></div>
          {n.match_id !== null && <button className="btn btn-sm" onClick={() => { if (!n.is_read) void api.markRead(n.id).then(unread.refresh); nav(`/matches?match=${n.match_id}`); }}>Open</button>}
          {!n.is_read && <button className="btn btn-ghost btn-sm" onClick={() => void api.markRead(n.id).then(done)}>Mark read</button>}
        </div>))}
    </>
  );
}

export default function Overview() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] ?? "lost") as Tab;
  const reports = useAsync(api.myReports, []);
  const claims = useAsync(api.recoveryRequests, []);
  const matches = useAsync(() => api.matches(true), []);
  const notes = useAsync(api.notifications, []);
  const reloadAll = () => { reports.reload(); claims.reload(); matches.reload(); };
  const lost = reports.data?.lost ?? [], found = reports.data?.found ?? [];
  const unread = (notes.data ?? []).filter(n => !n.is_read).length;
  const pending = (claims.data ?? []).filter(c => c.status === "PENDING").length;
  const potential = (matches.data ?? []).filter(m => !m.dismissed).length;

  return (
    <>
      <div className="page-head">
        <div><h1>Hi, {user?.name.split(" ")[0]}</h1><p>Your reports, matches and updates.</p></div>
        <div className="row"><Link className="btn" to="/report-found"><Icon name="box" size={15} />Found something</Link>
          <Link className="btn btn-primary" to="/report-lost"><Icon name="box" size={15} />Lost something</Link></div>
      </div>
      <div className="stats">
        <div className="stat"><div className="k">Lost reports</div><div className="v">{lost.length}</div><div className="s">{lost.filter(r => r.status === "ACTIVE").length} active</div></div>
        <div className="stat green"><div className="k">Found reports</div><div className="v">{found.length}</div><div className="s">{found.filter(r => r.status === "RECOVERED").length} returned</div></div>
        <div className="stat"><div className="k">Potential matches</div><div className="v">{potential}</div><div className="s">across your lost reports</div></div>
        <div className="stat green"><div className="k">Recovery requests</div><div className="v">{claims.data?.length ?? 0}</div><div className="s">{pending} pending review</div></div>
      </div>
      <div className="tabs" role="tablist">{TABS.map(([k, label]) => (
        <button key={k} role="tab" aria-selected={tab === k} className={`tab${tab === k ? " active" : ""}`} onClick={() => setParams({ tab: k })}>
          {label}{k === "notifications" && unread > 0 && <span className="badge">{unread}</span>}</button>))}</div>
      {tab === "lost" && <Async q={reports} empty={d => d.lost.length ? null : <Empty title="No lost reports yet."><p><Link to="/report-lost">Report a lost item</Link> and we will start looking.</p></Empty>}>
        {d => <>{d.lost.map(r => <LostCard key={r.id} r={r} reload={reloadAll} />)}</>}</Async>}
      {tab === "found" && <Async q={reports} empty={d => d.found.length ? null : <Empty title="No found reports yet."><p><Link to="/report-found">Report a found item</Link> to help an owner.</p></Empty>}>
        {d => <>{d.found.map(r => <FoundCard key={r.id} r={r} reload={reloadAll} />)}</>}</Async>}
      {tab === "recovery" && <Async q={claims}>{c => <Recovery claims={c} matches={matches.data ?? []} reload={reloadAll} />}</Async>}
      {tab === "notifications" && <Async q={notes}>{n => <Notes items={n} reload={notes.reload} />}</Async>}
    </>
  );
}
