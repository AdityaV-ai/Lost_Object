import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Match } from "../api/types";
import { Icon } from "../components/Icon";
import { Modal } from "../components/Modal";
import { SecureImage } from "../components/SecureImage";
import { Async, Empty, useAsync } from "../components/States";
import { SignalBars } from "../components/Widgets";
import { CUSTODY_TEXT, errorText, fmtDateTime, pct } from "../utils";

function ClaimBox({ m, onCancel }: { m: Match; onCancel: () => void }) {
  const c = m.claim;
  if (!c) return null;
  if (c.status === "PENDING") return (
    <div className="claimbox"><b><span className="dot" /> Pending staff review</b>
      You claimed this item. Campus staff will check your details and notify you — the finder never sees your name.
      <div style={{ marginTop: 8 }}><button className="btn btn-sm btn-danger" onClick={onCancel}>Cancel my claim</button></div></div>);
  if (c.status === "VERIFIED") return (
    <div className="claimbox green"><b><span className="dot" /> Verified — ready to collect</b>
      Staff confirmed it is yours. Collect it from the lost-and-found office with your ID.</div>);
  if (c.status === "COMPLETED") return <div className="claimbox green"><b>Returned to you</b>Recovery complete.</div>;
  if (c.status === "REJECTED") return <div className="claimbox red"><b>Claim declined</b>Staff could not verify this claim.</div>;
  return null;
}

function MatchCard({ m, flash, onChange }: { m: Match; flash: boolean; onChange: () => void }) {
  const [proofOpen, setProofOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const ref = useRef<HTMLElement>(null);
  useEffect(() => { if (flash) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [flash]);
  const open = m.claim && ["PENDING", "VERIFIED", "COMPLETED", "REJECTED"].includes(m.claim.status);
  const f = m.found;
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setMsg("");
    try { await fn(); onChange(); } catch (e) { setMsg(errorText(e)); } finally { setBusy(false); }
  };
  async function submitClaim(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const proof = String(new FormData(e.currentTarget).get("proof") ?? "").trim();
    setProofOpen(false);
    await act(() => api.claim(m.id, proof));
  }
  return (
    <article ref={ref} className={`card match${m.dismissed ? " dim" : ""}${flash ? " flash" : ""}`}>
      <div className="photo">
        <SecureImage load={f.has_image ? () => api.matchImage(m.id, "found") : null} alt={`Found: ${f.item_name}`} className="" deps={[m.id]} />
        {m.rank !== null && <span className="rank">#{m.rank}</span>}
      </div>
      <div className="match-body">
        <div className="match-title">
          <div><h3>{f.item_name}</h3>
            <span className="muted tiny"><Icon name="pin" size={13} /> {f.location ?? "Location not given"}</span></div>
          <div className="score"><b>{pct(m.fusion_score)}</b><span className="muted">%</span><small>relevance</small></div>
        </div>
        <div className="row">
          <span className={`chip ${m.label === "Strong match" ? "green" : ""}`}>{m.label}</span>
          {m.dismissed && <span className="chip">Dismissed</span>}
          {m.distance_m !== null && <span className="chip">{m.distance_m < 1000 ? `${Math.round(m.distance_m)} m away` : `${(m.distance_m / 1000).toFixed(1)} km away`}</span>}
        </div>
        <SignalBars m={m} />
        <details className="more"><summary>Item details</summary>
          <dl>
            <dt>Category</dt><dd>{f.category}</dd>
            {f.description && <><dt>Description</dt><dd>{f.description}</dd></>}
            {f.colour && <><dt>Colour</dt><dd>{f.colour}</dd></>}
            {f.distinguishing_features && <><dt>Features</dt><dd>{f.distinguishing_features}</dd></>}
            <dt>Where it is</dt><dd>{CUSTODY_TEXT[f.custody_status] ?? f.custody_status}</dd>
            <dt>Found</dt><dd>{fmtDateTime(f.occurred_at ?? f.reported_at)}</dd>
          </dl>
        </details>
        <ClaimBox m={m} onCancel={() => void act(() => api.cancelClaim(m.claim!.id))} />
        {msg && <div className="msg error" role="alert">{msg}</div>}
        {!open && !m.dismissed && (
          <div className="row" style={{ marginTop: "auto" }}>
            <button className="btn btn-primary" disabled={busy} style={{ flex: 1 }} onClick={() => setProofOpen(true)}><Icon name="hand" size={15} />Might be mine</button>
            <button className="btn" disabled={busy} style={{ flex: 1 }} onClick={() => void act(() => api.dismiss(m.id))}><Icon name="thumbDown" size={15} />Not mine</button>
          </div>)}
        {m.dismissed && <button className="btn" style={{ marginTop: "auto" }} disabled={busy} onClick={() => void act(() => api.restore(m.id))}>Restore this match</button>}
      </div>
      {proofOpen && (
        <Modal title="Claim this item" onClose={() => setProofOpen(false)}>
          <p className="muted">Tell staff something only the owner would know. It is shown to staff only, never to the finder. You can leave it blank, but staff may ask you later.</p>
          <form onSubmit={e => void submitClaim(e)} style={{ marginTop: 12 }}>
            <label>Proof of ownership (optional)
              <textarea name="proof" maxLength={1000} placeholder="e.g. a scratch near the bottom, lock-screen picture, what is inside…" /></label>
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
              <button type="button" className="btn" onClick={() => setProofOpen(false)}>Cancel</button>
              <button className="btn btn-primary">Send claim to staff</button></div>
          </form>
        </Modal>)}
    </article>
  );
}

export default function Matches() {
  const [params] = useSearchParams();
  const [showDismissed, setShowDismissed] = useState(false);
  const q = useAsync(() => api.matches(true), []);
  const flashId = Number(params.get("match")) || null;
  const lostFilter = Number(params.get("lost")) || null;

  const groups = useMemo(() => {
    const g = new Map<number, Match[]>();
    for (const m of q.data ?? []) {
      if (m.dismissed && !showDismissed) continue;
      if (lostFilter && m.lost_report.id !== lostFilter) continue;
      g.set(m.lost_report.id, [...(g.get(m.lost_report.id) ?? []), m]);
    }
    return [...g.values()];
  }, [q.data, showDismissed, lostFilter]);

  return (
    <>
      <div className="page-head">
        <div><h1>Potential matches</h1>
          <p>Ranked by relevance. A high score means the reports look alike — it is not proof of ownership. Staff verify every claim.</p></div>
        <label className="row" style={{ cursor: "pointer", fontWeight: 600 }}>
          <input type="checkbox" style={{ width: "auto", margin: 0 }} checked={showDismissed} onChange={e => setShowDismissed(e.target.checked)} />Show dismissed</label>
      </div>
      <Async q={q}>{() => groups.length === 0
        ? <Empty title="No potential matches yet.">
            <p>When a found report resembles one of your lost reports, it appears here and you get a notification.</p></Empty>
        : <>{groups.map(g => (
            <section key={g[0].lost_report.id} style={{ marginBottom: 34 }}>
              <div className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: 8, marginBottom: 16 }}>
                <span className="muted">For: <b style={{ color: "var(--text)" }}>{g[0].lost_report.item_name}</b> <span className="mono tiny">{g[0].lost_report.report_code}</span></span>
              </div>
              <div className="match-grid">{g.map(m => <MatchCard key={m.id} m={m} flash={m.id === flashId} onChange={q.reload} />)}</div>
            </section>))}</>}
      </Async>
    </>
  );
}
