import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Empty, ErrorBox, Loading, useAsync } from "../components/States";
import { SecureImage } from "../components/SecureImage";
import type { Report } from "../api/types";

type Tab = "lost" | "found" | "recovery" | "notifications";
const TABS: [Tab, string][] = [["lost", "My lost reports"], ["found", "My found reports"],
  ["recovery", "Recovery requests"], ["notifications", "Notifications"]];

const Card = ({ children }: { children: React.ReactNode }) => (
  <div className="card" style={{ padding: 16, margin: "10px 0", display: "flex", gap: 16, alignItems: "center" }}>{children}</div>
);

function ReportList({ rows, kind }: { rows: Report[]; kind: "lost" | "found" }) {
  if (!rows.length) return <Empty title="No records yet." />;
  return <>{rows.map(r => (
    <Card key={r.id}>
      {r.has_image && <SecureImage kind={kind} id={r.id} alt={r.item_name} />}
      <div><strong>{r.item_name}</strong> <span className="muted">· {r.category}</span>
        <p>{r.report_code} · {r.status}{r.custody_status ? ` · ${r.custody_status.replace(/_/g, " ").toLowerCase()}` : ""}</p>
        <small className="muted">{new Date(r.created_at).toLocaleString()}</small></div>
    </Card>))}</>;
}

function Panel({ tab }: { tab: Tab }) {
  const reports = useAsync(api.myReports, [tab === "lost" || tab === "found"]);
  const recovery = useAsync(api.recoveryRequests, []);
  const notes = useAsync(api.notifications, []);
  const q = tab === "recovery" ? recovery : tab === "notifications" ? notes : reports;
  if (q.loading) return <Loading />;
  if (q.error) return <ErrorBox message={q.error} onRetry={q.reload} />;
  if (tab === "lost") return <ReportList rows={reports.data!.lost} kind="lost" />;
  if (tab === "found") return <ReportList rows={reports.data!.found} kind="found" />;
  if (tab === "recovery") {
    const rows = recovery.data!;
    return rows.length ? <>{rows.map(r => <Card key={r.id}><div><strong>Recovery request #{r.id}</strong>
      <p>Match #{r.match_id} · {r.status} · <Link className="text-link" to={`/matches/${r.match_id}`}>View match</Link></p></div></Card>)}</>
      : <Empty title="No records yet." />;
  }
  const rows = notes.data!;
  return rows.length ? <>{rows.map(n => (
    <Card key={n.id}><div style={{ flex: 1 }}><strong>{n.title}{!n.is_read && " •"}</strong><p>{n.message}</p>
      <small className="muted">{new Date(n.created_at).toLocaleString()}</small></div>
      {!n.is_read && <button className="btn btn-light" onClick={() => api.markRead(n.id).then(notes.reload)}>Mark read</button>}
      <Link className="btn btn-light" to="/matches">View</Link></Card>))}</>
    : <Empty title="No records yet." />;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("lost");
  return (
    <main className="page-wrap">
      <div className="dashboard-heading">
        <div><span className="eyebrow">Your recovery space</span><h1>My dashboard</h1>
          <p className="muted">Welcome, {user?.name}. Your reports and updates in one place.</p></div>
        <div className="hero-actions"><Link className="btn btn-primary" to="/report-lost">＋ Lost item</Link>
          <Link className="btn btn-light" to="/report-found">＋ Found item</Link></div>
      </div>
      <div className="dashboard-tabs">{TABS.map(([k, label]) => (
        <button key={k} className={`tab${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>{label}</button>))}</div>
      <section className="data-panel"><Panel key={tab} tab={tab} /></section>
    </main>
  );
}
