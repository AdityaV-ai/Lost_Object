import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";

const CATEGORIES = ["Electronics", "Accessories", "Clothing", "Books & stationery", "Keys & cards", "Bags", "Other"];
const MAX = 5 * 1024 * 1024;

function useForm(submitFn: (fd: FormData) => Promise<string>, imageRequired: boolean) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; kind: "error" | "success" } | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  function onFile(file: File | undefined, input: HTMLInputElement) {
    if (preview) URL.revokeObjectURL(preview);
    if (!file) { setPreview(null); return; }
    if (file.size > MAX) { input.value = ""; setPreview(null); setMsg({ text: "Image must be 5 MB or smaller.", kind: "error" }); return; }
    setPreview(URL.createObjectURL(file));
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const file = fd.get("image") as File | null;
    if (imageRequired && (!file || !file.size)) { setMsg({ text: "Please select an image.", kind: "error" }); return; }
    if (file && !file.size) fd.delete("image");
    setBusy(true); setMsg(null);
    try {
      const text = await submitFn(fd);
      setMsg({ text, kind: "success" }); form.reset(); setPreview(null);
    } catch (err) {
      const e2 = err as ApiError;
      setMsg({ text: e2.details?.length ? e2.details.map(d => `${d.field}: ${d.message}`).join(" · ") : e2.message, kind: "error" });
    } finally { setBusy(false); }
  }
  return { busy, msg, preview, onFile, submit };
}

const CategorySelect = () => (
  <select name="category" required defaultValue="">
    <option value="">Choose a category</option>
    {CATEGORIES.map(c => <option key={c}>{c}</option>)}
  </select>
);

export function ReportLost() {
  const f = useForm(async fd => {
    const r = await api.createLost(fd);
    return `Report submitted successfully. Reference: ${r.report_code}. Potential matches found: ${r.matches_created}.`;
  }, false);
  return (
    <main className="page-wrap">
      <div className="page-intro"><span className="eyebrow">Tell us what happened</span><h1>Report a lost item</h1>
        <p>Share what you remember. Category and at least one of item name, description or photo are required.</p></div>
      <form className="form-card" onSubmit={f.submit}>
        <div className="form-grid">
          <label>Item name<input name="item_name" placeholder="e.g. Black wireless headphones" /></label>
          <label>Category <span className="required">*</span><CategorySelect /></label>
          <label>Colour<input name="colour" placeholder="e.g. Navy blue" /></label>
          <label>Brand / manufacturer<input name="brand" placeholder="If known" /></label>
          <label>Model<input name="model" placeholder="If known" /></label>
          <label>Last-seen location<input name="location" placeholder="Building, room or campus area" /></label>
          <label>Latitude (optional)<input name="latitude" type="number" step="any" min={-90} max={90} placeholder="e.g. 25.2048" /></label>
          <label>Longitude (optional)<input name="longitude" type="number" step="any" min={-180} max={180} placeholder="e.g. 55.2708" /></label>
          <label className="full">Distinguishing features<textarea name="distinguishing_features" rows={3} placeholder="Stickers, scratches, initials or other unique details" /></label>
          <label className="full">Additional description<textarea name="description" rows={4} placeholder="Anything else that may help identify your item" /></label>
          <label className="full">Photo (optional)
            <input type="file" name="image" accept=".jpg,.jpeg,.png,image/jpeg,image/png" onChange={e => f.onFile(e.target.files?.[0], e.target)} />
            <small className="hint">JPG or PNG, up to 5 MB. Only upload an image you are comfortable sharing with authorised staff.</small>
            {f.preview && <img className="preview" src={f.preview} alt="Selected image preview" />}
          </label>
        </div>
        {f.msg && <div className={`form-message ${f.msg.kind}`} role="status">{f.msg.text}</div>}
        <div className="form-footer"><Link className="text-link" to="/dashboard">Cancel</Link>
          <button className="btn btn-primary" type="submit" disabled={f.busy}>{f.busy ? "Submitting…" : "Submit lost report →"}</button></div>
      </form>
    </main>
  );
}

export function ReportFound() {
  const [custody, setCustody] = useState("");
  const f = useForm(async fd => {
    const r = await api.createFound(fd);
    return `Found report submitted. Reference: ${r.report_code}. Custody status: ${r.custody_status}. Potential matches found: ${r.matches_created}.`;
  }, true);
  return (
    <main className="page-wrap">
      <div className="page-intro"><span className="eyebrow">Thank you for helping</span><h1>Report a found item</h1>
        <p>A clear photo helps the recovery team identify the item. Found-item details are shared only through authorised workflows.</p></div>
      <form className="form-card" onSubmit={f.submit}>
        <div className="upload-box"><div className="upload-symbol">↑</div>
          <h3>Add a photo of the item <span className="required">*</span></h3><p>Choose a clear JPG or PNG image (up to 5 MB).</p>
          <input type="file" name="image" accept=".jpg,.jpeg,.png,image/jpeg,image/png" required onChange={e => f.onFile(e.target.files?.[0], e.target)} />
          {f.preview && <img className="preview" src={f.preview} alt="Selected image preview" />}</div>
        <div className="form-grid">
          <label>Item category <span className="required">*</span><CategorySelect /></label>
          <label>Item name <span className="required">*</span><input name="item_name" required placeholder="e.g. Water bottle" /></label>
          <label>Where found (optional)<input name="location" placeholder="Building, room or campus area" /></label>
          <label className="full">Short description<textarea name="description" rows={3} placeholder="Describe the item without revealing sensitive identifying details" /></label>
        </div>
        <fieldset className="custody-field"><legend>Where is the item now? <span className="required">*</span></legend>
          {[["LEFT_WHERE_FOUND", "Left where found", "The item remains at its original location."],
            ["TEMPORARILY_HOLDING", "Temporarily holding", "I am keeping it safe for now."],
            ["AWAITING_DEPOSIT_CONFIRMATION", "Deposited at authorised drop point", "Staff must confirm the physical deposit."]].map(([v, t, d]) => (
            <label className="choice" key={v}>
              <input type="radio" name="custody_status" value={v} required onChange={() => setCustody(v)} />
              <span><b>{t}</b><small>{d}</small></span></label>))}
          {custody === "AWAITING_DEPOSIT_CONFIRMATION" &&
            <p className="inline-note">Status will be shown as <b>Awaiting Deposit Confirmation</b> until authorised staff verify it.</p>}
        </fieldset>
        {f.msg && <div className={`form-message ${f.msg.kind}`} role="status">{f.msg.text}</div>}
        <div className="form-footer"><Link className="text-link" to="/dashboard">Cancel</Link>
          <button className="btn btn-primary" type="submit" disabled={f.busy}>{f.busy ? "Submitting…" : "Submit found report →"}</button></div>
      </form>
    </main>
  );
}
