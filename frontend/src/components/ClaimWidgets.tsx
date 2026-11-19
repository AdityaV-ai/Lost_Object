import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Claim, Match } from "../api/types";
import { errorText, fmtDateTime } from "../utils";
import { Icon } from "./Icon";
import { Modal } from "./Modal";

const MAX_BYTES = 5 * 1024 * 1024;

/** Optional photo with preview, replace/remove, and type/size validation (the server re-validates the contents). */
export function PhotoPicker({ file, onChange }: { file: File | null; onChange: (f: File | null) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState("");
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  function pick(f: File | undefined) {
    if (!f) return;
    if (!["image/png", "image/jpeg"].includes(f.type)) { setErr("Only JPG or PNG images are allowed."); return; }
    if (f.size > MAX_BYTES) { setErr("The image must be 5 MB or smaller."); return; }
    setErr(""); onChange(f);
  }
  return (
    <div className="photo-pick">
      <input ref={input} type="file" accept="image/png,image/jpeg" hidden onChange={e => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      {file && url ? (
        <div className="row" style={{ alignItems: "flex-start" }}>
          <img src={url} alt="Selected proof preview" className="proof-prev" />
          <div><div className="muted tiny">{file.name} · {(file.size / 1024).toFixed(0)} KB</div>
            <div className="row" style={{ marginTop: 6 }}>
              <button type="button" className="btn btn-sm" onClick={() => input.current?.click()}>Replace</button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => { onChange(null); setErr(""); }}>Remove</button></div></div>
        </div>
      ) : <button type="button" className="btn" onClick={() => input.current?.click()}><Icon name="image" size={15} />Add a photo (optional)</button>}
      {err && <div className="msg error" role="alert" style={{ marginTop: 8 }}>{err}</div>}
    </div>
  );
}

function Progress({ value }: { value: number }) {
  return <div className="progress" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${value}%` }} /><span>Uploading photo… {value}%</span></div>;
}

/** "Might be mine": explanation, distinguishing details and an optional photo. A photo is never required. */
export function ClaimForm({ m, onClose, onDone }: { m: Match; onClose: () => void; onDone: () => void }) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [partial, setPartial] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "").trim() || undefined;
    setBusy(true); setMsg("");
    let claim: Claim;
    try { claim = await api.claim(m.id, { proof: v("proof"), distinguishing_features: v("features"), additional_info: v("info") }); }
    catch (err) { setMsg(errorText(err)); setBusy(false); return; }
    if (photo) {
      const fd = new FormData(); fd.append("image", photo);
      try { setPct(0); await api.addEvidence(claim.id, fd, setPct); }
      catch (err) { setPartial(true); setMsg(`Your claim was sent, but the photo could not be uploaded: ${errorText(err)} You can add it later from the claim card.`); setBusy(false); setPct(null); return; }
    }
    onDone();
  }
  return (
    <Modal title="Claim this item" onClose={partial ? onDone : onClose}>
      <p className="muted">Tell staff why you believe it is yours. This is shown to staff only, never to the finder. Everything here is optional, but more detail helps staff verify you faster.</p>
      <form onSubmit={e => void submit(e)} style={{ marginTop: 12 }}>
        <label>Why do you believe it is yours?<textarea name="proof" maxLength={1000} placeholder="e.g. what is inside, when and where you lost it, lock-screen picture…" /></label>
        <label>Distinguishing characteristics<textarea name="features" maxLength={1000} placeholder="Scratches, stickers, engraving, serial number…" /></label>
        <label>Anything else staff should know<textarea name="info" maxLength={1000} /></label>
        <div style={{ margin: "10px 0" }}><b>Photo of the item or proof (optional)</b>
          <div className="muted tiny" style={{ marginBottom: 6 }}>JPG or PNG, up to 5 MB. Only you and staff can ever see it.</div>
          <PhotoPicker file={photo} onChange={setPhoto} /></div>
        {pct !== null && <Progress value={pct} />}
        {msg && <div className={`msg ${partial ? "success" : "error"}`} role="alert">{msg}</div>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button type="button" className="btn" onClick={partial ? onDone : onClose}>{partial ? "Close" : "Cancel"}</button>
          {!partial && <button className="btn btn-primary" disabled={busy}>{busy ? "Sending…" : "Send claim to staff"}</button>}</div>
      </form>
    </Modal>
  );
}

/** Add more evidence to an open claim (e.g. when staff ask for it). */
export function EvidenceForm({ claim, onClose, onDone }: { claim: Claim; onClose: () => void; onDone: () => void }) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!photo && !note.trim()) { setMsg("Add a photo or a written note."); return; }
    const fd = new FormData();
    if (note.trim()) fd.append("note", note.trim());
    if (photo) fd.append("image", photo);
    setBusy(true); setMsg(""); setPct(photo ? 0 : null);
    try { await api.addEvidence(claim.id, fd, setPct); onDone(); }
    catch (err) { setMsg(errorText(err)); setBusy(false); setPct(null); }
  }
  return (
    <Modal title="Add evidence" onClose={onClose}>
      {claim.staff_message && <div className="proof"><b>Staff asked</b><p>{claim.staff_message}</p></div>}
      <form onSubmit={e => void submit(e)} style={{ marginTop: 12 }}>
        <label>Explanation<textarea value={note} maxLength={1000} onChange={e => setNote(e.target.value)} placeholder="Describe what staff asked for…" /></label>
        <div style={{ margin: "10px 0" }}><PhotoPicker file={photo} onChange={setPhoto} /></div>
        {pct !== null && <Progress value={pct} />}
        {msg && <div className="msg error" role="alert">{msg}</div>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Sending…" : "Submit evidence"}</button></div>
      </form>
    </Modal>
  );
}

/** Where the owner stands and what to do next, including collection instructions once staff release them. */
export function ClaimStatus({ c, onCancel, onChange }: { c: Claim; onCancel: () => void; onChange: () => void }) {
  const [addOpen, setAddOpen] = useState(false);
  const col = c.collection;
  const cancel = <div style={{ marginTop: 8 }}><button className="btn btn-sm btn-danger" onClick={onCancel}>Cancel my claim</button></div>;
  let box: JSX.Element | null = null;
  switch (c.status) {
    case "PENDING":
    case "UNDER_REVIEW":
      box = <div className="claimbox"><b><span className="dot" /> {c.status === "PENDING" ? "Pending staff review" : "Staff are reviewing your claim"}</b>
        Campus staff will check your details and notify you. The finder never sees your name.
        {c.evidence_count > 0 && <> You attached {c.evidence_count} piece{c.evidence_count === 1 ? "" : "s"} of evidence.</>}
        <div className="row" style={{ marginTop: 8 }}><button className="btn btn-sm" onClick={() => setAddOpen(true)}>Add evidence</button>
          <button className="btn btn-sm btn-danger" onClick={onCancel}>Cancel my claim</button></div></div>;
      break;
    case "ADDITIONAL_EVIDENCE_REQUESTED":
      box = <div className="claimbox amber"><b><span className="dot" /> Staff need more evidence</b>
        {c.staff_message && <p style={{ margin: "4px 0" }}>“{c.staff_message}”</p>}
        <div className="row" style={{ marginTop: 8 }}><button className="btn btn-primary btn-sm" onClick={() => setAddOpen(true)}>Provide evidence</button>
          <button className="btn btn-sm btn-danger" onClick={onCancel}>Cancel my claim</button></div></div>;
      break;
    case "VERIFIED":
      box = <div className="claimbox green"><b><span className="dot" /> Approved</b>
        Staff accepted your claim. They are choosing where you can collect it; you will be notified with the address.{cancel}</div>;
      break;
    case "AWAITING_COLLECTION":
      box = <div className="claimbox green"><b><span className="dot" /> Ready to collect</b>
        {col && <div className="collect">
          <div><span className="muted tiny">Collect at</span><br /><b>{col.name}</b></div>
          {col.address && <div><span className="muted tiny">Address</span><br />{col.address}</div>}
          {col.instructions && <div><span className="muted tiny">Instructions</span><br />{col.instructions}</div>}
          <div><span className="muted tiny">Next step</span><br />Bring a photo ID and your claim details. Staff will confirm the handover.</div>
          {col.maps_url && <div className="row"><a className="btn btn-primary btn-sm" href={col.maps_url} target="_blank" rel="noreferrer noopener"><Icon name="pin" size={14} />Open in Google Maps</a>
            {col.osm_url && <a className="btn btn-sm" href={col.osm_url} target="_blank" rel="noreferrer noopener">OpenStreetMap</a>}</div>}
        </div>}{cancel}</div>;
      break;
    case "HANDED_OVER":
    case "COMPLETED":
      box = <div className="claimbox green"><b>Returned to you</b>Handed over {fmtDateTime(c.handed_over_at ?? c.completed_at)}. Recovery complete.</div>;
      break;
    case "REJECTED":
      box = <div className="claimbox red"><b>Claim declined</b>{c.rejection_reason ?? "Staff could not verify this claim."}</div>;
      break;
  }
  return <>{box}{addOpen && <EvidenceForm claim={c} onClose={() => setAddOpen(false)} onDone={() => { setAddOpen(false); onChange(); }} />}</>;
}
