import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { LocationPicker, type Place } from "../components/LocationPicker";
import { CATEGORIES, errorText } from "../utils";

const MAX = 5 * 1024 * 1024;
const EMPTY_PLACE: Place = { address: "", latitude: null, longitude: null };

function Step({ n, title, hint, children }: { n: number; title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="form-step">
      <div><span className="step-tag">Step {n}</span><h3>{title}</h3>{hint && <p className="muted tiny">{hint}</p>}</div>
      <div>{children}</div>
    </section>
  );
}

function Dropzone({ required, preview, onFile }: { required?: boolean; preview: string | null; onFile: (f: File | undefined, input: HTMLInputElement) => void }) {
  return (
    <div className="dropzone">
      <div className="ico"><Icon name="upload" /></div>
      <b>{required ? "Photo of the found item " : "Photo of the item "}{required && <span className="req">*</span>}</b>
      <p className="muted tiny">Drag &amp; drop or click · one JPG/PNG, up to 5 MB</p>
      <input type="file" name="image" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required={required} aria-label="Photo"
             onChange={e => onFile(e.target.files?.[0], e.target)} />
      {preview && <img src={preview} alt="Selected photo preview" />}
    </div>
  );
}

function usePhoto(setMsg: (m: string) => void) {
  const [preview, setPreview] = useState<string | null>(null);
  return {
    preview, reset: () => setPreview(null),
    onFile: (file: File | undefined, input: HTMLInputElement) => {
      if (preview) URL.revokeObjectURL(preview);
      if (!file) { setPreview(null); return; }
      if (file.size > MAX) { input.value = ""; setPreview(null); setMsg("Image must be 5 MB or smaller."); return; }
      setMsg(""); setPreview(URL.createObjectURL(file));
    },
  };
}

/** Builds the multipart body: drops empty fields, converts the local date-time to UTC, adds the place. */
function body(form: HTMLFormElement, place: Place): FormData {
  const fd = new FormData(form);
  const file = fd.get("image") as File | null;
  if (file && !file.size) fd.delete("image");
  for (const [k, v] of [...fd.entries()]) if (typeof v === "string" && v.trim() === "") fd.delete(k);
  const when = fd.get("occurred_at");
  if (typeof when === "string") fd.set("occurred_at", new Date(when).toISOString());
  if (place.address.trim()) fd.set("location", place.address.trim());
  if (place.latitude !== null && place.longitude !== null) {
    fd.set("latitude", String(place.latitude)); fd.set("longitude", String(place.longitude));
  }
  return fd;
}

const nowLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

function Category({ required }: { required?: boolean }) {
  return (
    <label>Category {required && <span className="req">*</span>}
      <select name="category" required defaultValue=""><option value="" disabled>Choose a category</option>
        {CATEGORIES.map(c => <option key={c}>{c}</option>)}</select></label>
  );
}

export function ReportLost() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState("");
  const [place, setPlace] = useState<Place>(EMPTY_PLACE);
  const photo = usePhoto(setMsg);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true); setMsg(""); setOk("");
    try {
      const r = await api.createLost(body(form, place));
      setOk(`Report ${r.report_code} submitted. ${r.matches_created > 0 ? `${r.matches_created} potential match${r.matches_created > 1 ? "es" : ""} found — see Matches.` : "No candidates yet; you will be notified when one appears."}`);
      form.reset(); setPlace(EMPTY_PLACE); photo.reset();
    } catch (err) { setMsg(errorText(err)); } finally { setBusy(false); }
  }
  return (
    <div className="form-page">
      <div className="page-head"><div><h1>Report a lost item</h1>
        <p>Tell us what you remember. A photo helps, but a good description and a place are enough.</p></div></div>
      <form onSubmit={e => void submit(e)}>
        <Step n={1} title="What did you lose?" hint="Category is required, plus at least one of: name, description or photo.">
          <div className="grid2">
            <label>Item name<input name="item_name" placeholder="e.g. Black wireless headphones" /></label>
            <Category required />
            <label>Colour<input name="colour" placeholder="e.g. Navy blue" /></label>
            <label>Brand<input name="brand" placeholder="If known" /></label>
            <label>Model<input name="model" placeholder="If known" /></label>
            <label>When did you lose it?<input type="datetime-local" name="occurred_at" max={nowLocal()} /></label>
            <label className="full">Distinguishing features
              <textarea name="distinguishing_features" placeholder="Stickers, scratches, initials…" />
              <span className="hint">The details only the owner would know help staff verify the claim.</span></label>
            <label className="full">Description<textarea name="description" placeholder="Anything else that may help identify it" /></label>
          </div>
        </Step>
        <Step n={2} title="Add a photo" hint="Optional. A photo of the item, or a similar one, greatly improves matching. Without one, your description is compared with finders' photos.">
          <Dropzone preview={photo.preview} onFile={photo.onFile} />
        </Step>
        <Step n={3} title="Where did you last have it?" hint="Optional. It only helps rank candidates by distance.">
          <LocationPicker label="Last seen" value={place} onChange={setPlace} />
        </Step>
        {msg && <div className="msg error" role="alert">{msg}</div>}
        {ok && <div className="msg success" role="status">{ok} <Link to="/dashboard">Go to overview</Link></div>}
        <div className="sticky-actions"><Link className="btn" to="/dashboard">Cancel</Link>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Submitting… (matching can take a few seconds)" : "Submit lost report"}</button></div>
      </form>
    </div>
  );
}

const CUSTODY: [string, string, string][] = [
  ["LEFT_WHERE_FOUND", "Left where found", "I saw it but did not pick it up."],
  ["TEMPORARILY_HOLDING", "I'm holding it", "I picked it up and am keeping it safe."],
  ["AWAITING_DEPOSIT_CONFIRMATION", "Deposited at a drop point", "Staff will confirm they received it."],
];

export function ReportFound() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState("");
  const [place, setPlace] = useState<Place>(EMPTY_PLACE);
  const photo = usePhoto(setMsg);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true); setMsg(""); setOk("");
    try {
      const r = await api.createFound(body(form, place));
      setOk(`Report ${r.report_code} submitted — thank you! ${r.matches_created} possible owner${r.matches_created === 1 ? " was" : "s were"} notified.`);
      form.reset(); setPlace(EMPTY_PLACE); photo.reset();
    } catch (err) { setMsg(errorText(err)); } finally { setBusy(false); }
  }
  return (
    <div className="form-page">
      <div className="page-head"><div><h1>Report a found item</h1>
        <p>A clear photo is the key. Owners are matched privately; nothing is shown publicly.</p></div></div>
      <form onSubmit={e => void submit(e)}>
        <Step n={1} title="Take or upload a photo" hint="Required. A clear photo from the front works best.">
          <Dropzone required preview={photo.preview} onFile={photo.onFile} />
        </Step>
        <Step n={2} title="Where is the item now?">
          <div className="custody" role="radiogroup" aria-label="Item custody">
            {CUSTODY.map(([v, t, d], i) => (
              <label key={v}><input type="radio" name="custody_status" value={v} defaultChecked={i === 0} />
                <span className="opt"><b>{t}</b><small>{d}</small></span></label>))}
          </div>
        </Step>
        <Step n={3} title="Details" hint="Category and name are required. Describe the item without revealing details only the owner should know.">
          <div className="grid2">
            <Category required />
            <label>Item name <span className="req">*</span><input name="item_name" required placeholder="e.g. Water bottle" /></label>
            <label>Colour<input name="colour" placeholder="e.g. Dark green" /></label>
            <label>When did you find it?<input type="datetime-local" name="occurred_at" max={nowLocal()} /></label>
            <label className="full">Short description<textarea name="description" placeholder="Shape, size, material, visible brand…" /></label>
            <label className="full">Distinguishing features<textarea name="distinguishing_features" placeholder="Stickers, scratches… (staff use this to verify the owner)" /></label>
          </div>
        </Step>
        <Step n={4} title="Where did you find it?" hint="Optional, but it helps match it with the right owner.">
          <LocationPicker label="Found at" value={place} onChange={setPlace} />
        </Step>
        {msg && <div className="msg error" role="alert">{msg}</div>}
        {ok && <div className="msg success" role="status">{ok} <Link to="/dashboard?tab=found">View my found reports</Link></div>}
        <div className="sticky-actions"><Link className="btn" to="/dashboard">Cancel</Link>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Submitting… (matching can take a few seconds)" : "Submit found report"}</button></div>
      </form>
    </div>
  );
}
