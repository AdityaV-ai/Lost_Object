import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Empty, ErrorBox, Loading, useAsync } from "../components/States";

const pct = (v: number | null) => (v === null ? "n/a" : `${(v * 100).toFixed(1)}%`);

export function Matches() {
  const { data, error, loading, reload } = useAsync(api.matches);
  return (
    <main className="page-wrap">
      <div className="page-intro"><span className="eyebrow">Private to your account</span><h1>Potential matches</h1>
        <p>These candidates are ranked by available matching signals. A relevance score is not proof of ownership.</p></div>
      <section className="data-panel">
        {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> :
          !data!.length ? <Empty title="No potential matches yet.">
            <p>When a found report resembles one of your lost reports, it will appear here.</p></Empty> :
          data!.map(m => (
            <Link key={m.id} to={`/matches/${m.id}`} className="card" style={{ display: "block", padding: 16, margin: "12px 0" }}>
              <strong>{m.found_item_name}</strong> — {pct(m.fusion_score)} relevance
              <span className="muted"> · for {m.lost_report.report_code} ({m.lost_report.item_name})</span>
              {m.interest_status && <span className="muted"> · interest {m.interest_status.toLowerCase()}</span>}
            </Link>))}
      </section>
    </main>
  );
}

export function MatchDetail() {
  const id = Number(useParams().id);
  const { data: m, error, loading, reload } = useAsync(() => api.match(id), [id]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function interest() {
    setBusy(true); setMsg("");
    try { setStatus((await api.interest(id)).status); }
    catch (e) { setMsg((e as Error).message); }
    finally { setBusy(false); }
  }
  const current = status ?? m?.interest_status ?? null;
  return (
    <main className="page-wrap">
      <div className="page-intro"><Link className="text-link" to="/matches">← Back</Link>
        <span className="eyebrow">Review carefully</span><h1>Potential match details</h1>
        <p>Ownership is verified by authorised staff, never by an AI score.</p></div>
      <section className="data-panel">
        {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : m && (<>
          <h3>{m.found_item_name} <span className="muted">· {m.found_category}</span></h3>
          <p>Related lost report: {m.lost_report.report_code} ({m.lost_report.item_name})</p>
          <p>Relevance score: <b>{pct(m.fusion_score)}</b> (not ownership probability)</p>
          <ul>
            <li>Image similarity: {pct(m.image_similarity)}</li>
            <li>Text similarity: {pct(m.text_similarity)}</li>
            <li>Location similarity: {pct(m.location_similarity)}</li>
          </ul>
          <small className="muted">“n/a” means that signal was unavailable and the score was computed from the remaining signals.</small>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={interest} disabled={busy || current !== null}>
              {current ? `Interest submitted (${current.toLowerCase()})` : busy ? "Submitting…" : "Express interest"}</button>
          </div>
          {msg && <div className="form-message error" role="alert">{msg}</div>}
        </>)}
      </section>
    </main>
  );
}
