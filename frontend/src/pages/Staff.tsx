import { useState } from "react";
import { api } from "../api/client";
import { Empty, ErrorBox, Loading, useAsync } from "../components/States";

export default function Staff() {
  const { data, error, loading, reload } = useAsync(api.pendingDeposits);
  const [msg, setMsg] = useState("");
  async function confirm(id: number) {
    setMsg("");
    try { await api.confirmDeposit(id); reload(); } catch (e) { setMsg((e as Error).message); }
  }
  return (
    <main className="page-wrap">
      <div className="page-intro"><span className="eyebrow">Authorised personnel</span><h1>Staff workspace</h1>
        <p>Confirm physical deposits of found items. Access is enforced by the backend.</p></div>
      <section className="data-panel">
        {msg && <div className="form-message error" role="alert">{msg}</div>}
        {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> :
          !data!.length ? <Empty title="No deposits awaiting confirmation." /> :
          data!.map(r => (
            <div className="card" key={r.id} style={{ padding: 16, margin: "10px 0", display: "flex", gap: 16, alignItems: "center" }}>
              <div style={{ flex: 1 }}><strong>{r.item_name}</strong> <span className="muted">· {r.category}</span>
                <p>{r.report_code} · reported {new Date(r.created_at).toLocaleString()}</p></div>
              <button className="btn btn-primary" onClick={() => confirm(r.id)}>Confirm deposit</button>
            </div>))}
      </section>
    </main>
  );
}
