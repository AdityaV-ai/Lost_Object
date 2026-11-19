import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Analytics, PendingDeposit, RecoveryCase, Report } from "../api/types";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { SecureImage } from "../components/SecureImage";
import { Async, Empty, useAsync } from "../components/States";
import { SignalBars } from "../components/Widgets";
import { CUSTODY_TEXT, download, errorText, fmtDateTime, pct, statusChip } from "../utils";

const TABS = [["analytics", "Analytics"], ["claims", "Recovery requests"], ["deposits", "Deposits"], ["reports", "Reports"],
  ["people", "People"], ["matching", "Matching activity"], ["log", "Staff log"]] as const;
type TabKey = (typeof TABS)[number][0];

const Chip = ({ status }: { status: string }) => { const c = statusChip(status); return <span className={`chip ${c.cls}`}><span className="dot" />{c.text}</span>; };

function Seg<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return <div className="seg">{options.map(([v, l]) => <button key={v} className={value === v ? "active" : ""} onClick={() => onChange(v)}>{l}</button>)}</div>;
}
const Search = ({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) =>
  <input className="search" type="search" value={value} placeholder={placeholder} aria-label={placeholder} onChange={e => onChange(e.target.value)} />;

function ExportBtn({ what }: { what: string }) {
  return <button className="btn btn-sm" onClick={() => void api.staff.exportCsv(what).then(b => download(b, `findback-${what}.csv`))}>
    <Icon name="download" size={14} />Export CSV</button>;
}

/* ---------------- analytics ---------------- */
function Columns({ data, keys }: { data: { label: string; a: number; b?: number }[]; keys?: [string, string] }) {
  const max = Math.max(1, ...data.flatMap(d => [d.a, d.b ?? 0]));
  return (
    <div>
      <div className="cols" role="img" aria-label={data.map(d => `${d.label}: ${d.a}${d.b !== undefined ? ` / ${d.b}` : ""}`).join(", ")}>
        {data.map(d => (
          <div key={d.label}><span>{d.a || ""}</span><i style={{ height: `${(d.a / max) * 80}%` }} />
            {d.b !== undefined && <><span>{d.b || ""}</span><i className="b" style={{ height: `${(d.b / max) * 80}%` }} /></>}
            <span>{d.label}</span></div>))}
      </div>
      {keys && <p className="muted tiny" style={{ marginTop: 8 }}><span style={{ color: "var(--primary)" }}>■</span> {keys[0]} <span style={{ color: "var(--success)" }}>■</span> {keys[1]}</p>}
    </div>
  );
}

function AnalyticsView({ a }: { a: Analytics }) {
  return (
    <>
      <div className="stats">
        <div className="stat"><div className="k">Recovery rate</div><div className="v">{a.recovery_rate === null ? "—" : `${Math.round(a.recovery_rate * 100)}%`}</div><div className="s">{a.totals.recovered} of {a.totals.lost} lost reports returned</div></div>
        <div className="stat green"><div className="k">Avg time to return</div><div className="v">{a.avg_hours_to_complete === null ? "—" : `${a.avg_hours_to_complete} h`}</div><div className="s">claim to completed handover</div></div>
        <div className="stat"><div className="k">Matches generated</div><div className="v">{a.totals.matches}</div><div className="s">{a.totals.claims} claims</div></div>
        <div className="stat green"><div className="k">Users</div><div className="v">{a.totals.users}</div><div className="s">{a.totals.lost} lost · {a.totals.found} found reports</div></div>
      </div>
      <div className="charts">
        <div className="card chart"><h3>Reports, last 14 days</h3>
          <Columns keys={["Lost", "Found"]} data={a.reports_per_day.map(d => ({ label: d.date.slice(8), a: d.lost, b: d.found }))} /></div>
        <div className="card chart"><h3>Match relevance bands</h3>
          <Columns data={Object.entries(a.matches_by_score_band).map(([label, n]) => ({ label, a: n }))} /></div>
        <div className="card chart"><h3>Claims by status</h3>
          {Object.keys(a.claims_by_status).length === 0 ? <p className="muted">No claims yet.</p> :
            <div className="bars">{Object.entries(a.claims_by_status).map(([s, n]) => (
              <div className="sig" key={s} style={{ gridTemplateColumns: "110px 1fr 30px" }}><span>{statusChip(s).text}</span>
                <div className="bar"><i style={{ width: `${(n / Math.max(...Object.values(a.claims_by_status))) * 100}%` }} /></div><span>{n}</span></div>))}</div>}</div>
        <div className="card chart"><h3>Top categories</h3>
          {a.reports_by_category.length === 0 ? <p className="muted">No reports yet.</p> :
            <div className="bars">{a.reports_by_category.map(c => (
              <div className="sig" key={c.category} style={{ gridTemplateColumns: "130px 1fr 60px" }}><span>{c.category}</span>
                <div className="bar"><i style={{ width: `${((c.lost + c.found) / (a.reports_by_category[0].lost + a.reports_by_category[0].found)) * 100}%` }} /></div>
                <span>{c.lost}L / {c.found}F</span></div>))}</div>}</div>
      </div>
    </>
  );
}

/* ---------------- claims ---------------- */
function ReportFacts({ r, kind, place }: { r: Report; kind: "lost" | "found"; place?: string | null }) {
  return (
    <div>
      <SecureImage load={r.has_image ? () => api.reportImage(kind, r.id) : null} alt={`${kind} ${r.report_code}`} className="fimg" deps={[r.id]} />
      <p style={{ marginTop: 8 }}><span className="chip blue">{kind === "lost" ? "Lost report" : "Found item"}</span> <b className="mono">{r.report_code}</b></p>
      <h3 style={{ marginTop: 4 }}>{r.item_name}</h3>
      <div className="kv">
        <div><span>Category</span>{r.category}</div>
        {r.colour && <div><span>Colour</span>{r.colour}</div>}
        {r.brand && <div><span>Brand</span>{r.brand}</div>}
        {r.model && <div><span>Model</span>{r.model}</div>}
        {r.custody_status && <div><span>Custody</span>{CUSTODY_TEXT[r.custody_status] ?? r.custody_status}</div>}
        {(place ?? r.location) && <div><span>Place</span>{place ?? r.location}</div>}
        <div><span>When</span>{fmtDateTime(r.occurred_at ?? r.created_at)}</div>
        {r.description && <div className="full" style={{ gridColumn: "1 / -1" }}><span>Description</span>{r.description}</div>}
        {r.distinguishing_features && <div style={{ gridColumn: "1 / -1" }}><span>Distinguishing features</span>{r.distinguishing_features}</div>}
      </div>
    </div>
  );
}

function CaseDrawer({ c, onClose, onAct }: { c: RecoveryCase; onClose: () => void; onAct: (a: "verify" | "reject" | "complete") => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const run = async (a: "verify" | "reject" | "complete") => { setBusy(true); setMsg(""); try { await onAct(a); onClose(); } catch (e) { setMsg(errorText(e)); setBusy(false); } };
  return (
    <Modal side title={`Claim #${c.id}`} onClose={onClose}>
      <div className="row"><Chip status={c.status} /><span className="chip">{pct(c.fusion_score)}% relevance</span>
        <span className="muted tiny">Requested {fmtDateTime(c.created_at)}</span></div>
      <div className="proof"><b>Owner's proof</b><p>{c.proof ?? "The owner did not add any detail. Ask them to describe the item before verifying."}</p></div>
      <div className="row">
        {c.status === "PENDING" && <><button className="btn btn-primary" disabled={busy} onClick={() => void run("verify")}><Icon name="shield" size={15} />Verify owner</button>
          <button className="btn btn-danger" disabled={busy} onClick={() => void run("reject")}><Icon name="x" size={15} />Reject</button></>}
        {c.status === "VERIFIED" && <button className="btn btn-primary" disabled={busy} onClick={() => void run("complete")}><Icon name="check" size={15} />Mark as handed over</button>}
      </div>
      {msg && <div className="msg error" role="alert">{msg}</div>}
      <p className="muted tiny" style={{ margin: "18px 0 0", fontWeight: 700, letterSpacing: ".04em" }}>LOST VS FOUND</p>
      <div className="lvf"><ReportFacts r={c.lost_report} kind="lost" /><ReportFacts r={c.found_report} kind="found" place={c.found_location} /></div>
      <div className="lvf">
        <div className="party"><b>Owner</b><br />{c.owner.name}<br /><span className="muted">{c.owner.email}</span></div>
        <div className="party"><b>Finder</b><br />{c.finder.name}<br /><span className="muted">{c.finder.email}</span></div>
      </div>
    </Modal>
  );
}

function Claims({ reloadSummary }: { reloadSummary: () => void }) {
  const [status, setStatus] = useState("PENDING");
  const [q, setQ] = useState("");
  const list = useAsync(() => api.staff.cases(status, q), [status, q]);
  const [open, setOpen] = useState<RecoveryCase | null>(null);
  const act = async (id: number, a: "verify" | "reject" | "complete") => { await api.staff.caseAction(id, a); list.reload(); reloadSummary(); };
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <Seg value={status} onChange={setStatus} options={[["PENDING", "Pending"], ["VERIFIED", "Verified"], ["COMPLETED", "Completed"], ["REJECTED", "Rejected"], ["CANCELLED", "Cancelled"], ["ALL", "All"]]} />
        <div className="row"><Search value={q} onChange={setQ} placeholder="Search code, item, owner, finder…" /><ExportBtn what="claims" /></div>
      </div>
      <Async q={list} empty={d => d.length ? null : <Empty title="No claims in this view." />}>
        {cases => <>{cases.map(c => (
          <article className="card report" key={c.id}>
            <div className="report-top" style={{ alignItems: "stretch" }}>
              <SecureImage load={c.lost_report.has_image ? () => api.reportImage("lost", c.lost_report.id) : null} alt="lost" className="thumb" deps={[c.id]} />
              <div className="report-body"><span className="muted tiny">Lost report · <b className="mono">{c.lost_report.report_code}</b></span><h3>{c.lost_report.item_name}</h3>
                <p className="muted tiny">Owner: {c.owner.name} · {c.owner.email}</p></div>
              <SecureImage load={c.found_report.has_image ? () => api.reportImage("found", c.found_report.id) : null} alt="found" className="thumb" deps={[c.id]} />
              <div className="report-body"><span className="muted tiny">Found item · <b className="mono">{c.found_report.report_code}</b></span><h3>{c.found_report.item_name}</h3>
                <p className="muted tiny">Finder: {c.finder.name} · {c.finder.email}</p></div>
              <div className="report-actions" style={{ alignItems: "flex-end" }}><Chip status={c.status} />
                <span className="chip">{pct(c.fusion_score)}% relevance</span>
                <span className="chip">{CUSTODY_TEXT[c.found_report.custody_status ?? ""] ?? c.found_report.custody_status}</span></div>
            </div>
            <div className="proof" style={{ margin: "0 18px" }}><b>Owner's proof:</b> {c.proof ?? "none given"}</div>
            <div className="row" style={{ justifyContent: "space-between", padding: "12px 18px 16px" }}>
              <span className="muted tiny">Requested {fmtDateTime(c.created_at)}</span>
              <div className="row"><button className="btn btn-sm" onClick={() => setOpen(c)}>View details</button>
                {c.status === "PENDING" && <><button className="btn btn-primary btn-sm" onClick={() => void act(c.id, "verify")}><Icon name="shield" size={14} />Verify owner</button>
                  <button className="btn btn-danger btn-sm" onClick={() => void act(c.id, "reject")}><Icon name="x" size={14} />Reject</button></>}
                {c.status === "VERIFIED" && <button className="btn btn-primary btn-sm" onClick={() => void act(c.id, "complete")}>Mark as handed over</button>}</div>
            </div>
          </article>))}
          {open && <CaseDrawer c={open} onClose={() => setOpen(null)} onAct={a => act(open.id, a)} />}</>}
      </Async>
    </>
  );
}

/* ---------------- deposits ---------------- */
function Deposits({ reloadSummary }: { reloadSummary: () => void }) {
  const q = useAsync(api.staff.deposits, []);
  const [msg, setMsg] = useState("");
  const confirm = async (d: PendingDeposit) => {
    try { await api.staff.confirmDeposit(d.id); q.reload(); reloadSummary(); } catch (e) { setMsg(errorText(e)); }
  };
  return (
    <>
      {msg && <div className="msg error" role="alert">{msg}</div>}
      <Async q={q} empty={d => d.length ? null : <Empty title="No deposits awaiting confirmation." />}>
        {rows => <div className="match-grid">{rows.map(d => (
          <article className="card match" key={d.id}>
            <div className="photo"><SecureImage load={d.has_image ? () => api.reportImage("found", d.id) : null} alt={d.item_name} className="" deps={[d.id]} /></div>
            <div className="match-body">
              <span className="mono muted tiny">{d.report_code}</span><h3>{d.item_name}</h3>
              <span className="muted tiny"><Icon name="pin" size={13} /> {d.location ?? "Location not given"}</span>
              <span className="muted tiny">By {d.finder.name} · {fmtDateTime(d.created_at)} · {d.match_count} match{d.match_count === 1 ? "" : "es"}</span>
              <button className="btn btn-primary" style={{ marginTop: "auto" }} onClick={() => void confirm(d)}><Icon name="check" size={15} />Confirm received</button>
            </div></article>))}</div>}
      </Async>
    </>
  );
}

/* ---------------- tables ---------------- */
function Reports() {
  const [kind, setKind] = useState<"lost" | "found">("lost");
  const [status, setStatus] = useState("ALL");
  const [q, setQ] = useState("");
  const list = useAsync(() => api.staff.reports(kind, status, q), [kind, status, q]);
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <div className="row"><Seg value={kind} onChange={setKind} options={[["lost", "Lost"], ["found", "Found"]]} />
          <Seg value={status} onChange={setStatus} options={[["ALL", "All"], ["ACTIVE", "Active"], ["RECOVERED", "Returned"], ["RESOLVED", "Found by owner"]]} /></div>
        <div className="row"><Search value={q} onChange={setQ} placeholder="Search code, item, person…" /><ExportBtn what={`${kind}-reports`} /></div>
      </div>
      <Async q={list} empty={d => d.length ? null : <Empty title="No reports match." />}>{rows => (
        <div className="card table-wrap"><table><thead><tr><th>Code</th><th>Item</th><th>Category</th><th>Status</th>{kind === "found" && <th>Custody</th>}<th>Reporter</th><th>Matches</th><th>Created</th></tr></thead>
          <tbody>{rows.map(r => (<tr key={r.id}><td className="mono">{r.report_code}</td><td>{r.item_name}</td><td>{r.category}</td><td><Chip status={r.status} /></td>
            {kind === "found" && <td>{CUSTODY_TEXT[r.custody_status ?? ""] ?? r.custody_status}</td>}<td>{r.owner.name}</td><td>{r.match_count}</td><td>{fmtDateTime(r.created_at)}</td></tr>))}</tbody></table></div>)}</Async>
    </>
  );
}

function People() {
  const [q, setQ] = useState("");
  const list = useAsync(() => api.staff.people(q), [q]);
  return (
    <>
      <div style={{ marginBottom: 14 }}><Search value={q} onChange={setQ} placeholder="Search name, email, role…" /></div>
      <Async q={list} empty={d => d.length ? null : <Empty title="Nobody matches." />}>{rows => (
        <div className="card table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Lost</th><th>Found</th><th>Joined</th></tr></thead>
          <tbody>{rows.map(p => (<tr key={p.id}><td>{p.name}</td><td>{p.email}</td><td><span className={`chip ${p.role === "staff" ? "blue" : ""}`}>{p.role}</span></td>
            <td>{p.lost_count}</td><td>{p.found_count}</td><td>{fmtDateTime(p.created_at)}</td></tr>))}</tbody></table></div>)}</Async>
    </>
  );
}

function Matching() {
  const [filter, setFilter] = useState("all");
  const [min, setMin] = useState("0");
  const [q, setQ] = useState("");
  const list = useAsync(() => api.staff.matches(filter, Number(min) || undefined, q), [filter, min, q]);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <div className="row"><Seg value={filter} onChange={setFilter} options={[["all", "All"], ["unclaimed", "Not claimed"], ["claimed", "Claimed"], ["dismissed", "Dismissed"]]} />
          <select style={{ width: "auto", marginTop: 0 }} value={min} onChange={e => setMin(e.target.value)} aria-label="Minimum score">
            <option value="0">Any score</option><option value="0.5">50%+</option><option value="0.75">75%+</option></select></div>
        <div className="row"><Search value={q} onChange={setQ} placeholder="Search report code or item…" /><ExportBtn what="matches" /></div>
      </div>
      <Async q={list} empty={d => d.length ? null : <Empty title="No matches in this view." />}>{rows => (<>
        <p className="muted tiny" style={{ marginBottom: 8 }}>{rows.length} matches · click a row for the signal breakdown. “—” = signal unavailable (excluded from the score).</p>
        <div className="card table-wrap"><table><thead><tr><th>When</th><th>Lost</th><th>Found</th><th>Photo</th><th>Words↔photo</th><th>Text</th><th>Location</th><th>Final</th><th>Owner status</th></tr></thead>
          <tbody>{rows.map(r => (<tr className="click" key={r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>
            <td>{fmtDateTime(r.created_at)}</td><td><span className="mono">{r.lost_code}</span> {r.lost_name}</td><td><span className="mono">{r.found_code}</span> {r.found_name}</td>
            <td>{pct(r.image_similarity)}{r.image_similarity !== null && "%"}</td><td>{pct(r.words_photo_similarity)}{r.words_photo_similarity !== null && "%"}</td>
            <td>{pct(r.text_similarity)}{r.text_similarity !== null && "%"}</td><td>{pct(r.location_similarity)}{r.location_similarity !== null && "%"}</td>
            <td><b>{pct(r.fusion_score)}%</b></td><td>{r.dismissed ? <span className="chip">Dismissed</span> : r.claim_status ? <Chip status={r.claim_status} /> : "—"}</td></tr>))}</tbody></table></div>
        {open !== null && (() => { const r = rows.find(x => x.id === open); return r ? (
          <div className="card chart" style={{ marginTop: 14 }}><h3>{r.lost_code} ↔ {r.found_code}</h3><SignalBars m={r} /></div>) : null; })()}
      </>)}</Async>
    </>
  );
}

function Log() {
  const [target, setTarget] = useState("all");
  const [q, setQ] = useState("");
  const list = useAsync(() => api.staff.log(target, q), [target, q]);
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <Seg value={target} onChange={setTarget} options={[["all", "All"], ["claim", "Claims"], ["found", "Found"]]} />
        <div className="row"><Search value={q} onChange={setQ} placeholder="Search code, staff name, note…" /><ExportBtn what="log" /></div>
      </div>
      <Async q={list} empty={d => d.length ? null : <Empty title="No staff actions recorded yet." />}>{rows => <>{rows.map(a => (
        <div className="card item" key={a.id}><span className="dot" style={{ color: "var(--success)" }} />
          <div className="grow"><b>{a.action.replace(/_/g, " ").toLowerCase().replace(/^./, c => c.toUpperCase())}</b> <span className="mono tiny">{a.code}</span> by {a.staff_name}
            <div className="muted tiny">{a.detail}</div></div><span className="muted tiny">{fmtDateTime(a.created_at)}</span></div>))}</>}</Async>
    </>
  );
}

/* ---------------- page ---------------- */
export default function Staff() {
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find(([k]) => k === params.get("tab"))?.[0] ?? "claims") as TabKey;
  const summary = useAsync(api.staff.summary, []);
  const analytics = useAsync(api.staff.analytics, []);
  const s = summary.data;
  const badge = (k: TabKey): ReactNode => (k === "claims" && s?.claims_to_verify ? <span className="badge">{s.claims_to_verify}</span>
    : k === "deposits" && s?.deposits_to_confirm ? <span className="badge">{s.deposits_to_confirm}</span> : null);
  return (
    <>
      <div className="page-head"><div><h1>Staff workspace</h1><p>Verify claims, confirm deposits and follow what the matcher is doing.</p></div></div>
      <div className="stats">
        <div className="stat"><div className="k">Claims to verify</div><div className="v">{s?.claims_to_verify ?? "—"}</div><div className="s">waiting for staff</div></div>
        <div className="stat green"><div className="k">Verified, awaiting handover</div><div className="v">{s?.verified_awaiting_handover ?? "—"}</div><div className="s">owner to collect</div></div>
        <div className="stat"><div className="k">Deposits to confirm</div><div className="v">{s?.deposits_to_confirm ?? "—"}</div><div className="s">at drop points</div></div>
        <div className="stat green"><div className="k">Finders holding items</div><div className="v">{s?.finders_holding_items ?? "—"}</div><div className="s">still with the finder</div></div>
      </div>
      <div className="tabs" role="tablist">{TABS.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={tab === k} className={`tab${tab === k ? " active" : ""}`} onClick={() => setParams({ tab: k })}>{l}{badge(k)}</button>))}</div>
      {tab === "analytics" && <Async q={analytics}>{a => <AnalyticsView a={a} />}</Async>}
      {tab === "claims" && <Claims reloadSummary={() => { summary.reload(); analytics.reload(); }} />}
      {tab === "deposits" && <Deposits reloadSummary={summary.reload} />}
      {tab === "reports" && <Reports />}
      {tab === "people" && <People />}
      {tab === "matching" && <Matching />}
      {tab === "log" && <Log />}
    </>
  );
}
