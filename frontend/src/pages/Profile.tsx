import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Async, Empty, useAsync } from "../components/States";
import { errorText, fmtDateTime, pct, statusChip } from "../utils";

const KIND_COLOR: Record<string, string> = { lost: "var(--primary)", found: "var(--success)", claim: "var(--primary)", staff: "var(--muted)" };
const hrs = (h: number | null) => (h === null ? "—" : h >= 48 ? `${(h / 24).toFixed(1)} d` : `${h} h`);

export default function Profile() {
  const { user, setUser } = useAuth();
  const q = useAsync(api.profile, []);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    try { setUser(await api.rename(name)); setEditing(false); setErr(null); q.reload(); } catch (e) { setErr(errorText(e)); }
  };
  return (
    <>
      <div className="page-head"><div><h1>My profile</h1><p>Your account and everything you have reported on FindBack.</p></div></div>
      <Async q={q}>{p => {
        const max = Math.max(1, ...p.categories.map(c => c.count));
        const st = Object.entries(p.claims.by_status);
        return (
          <>
            <div className="card" style={{ padding: 18, marginBottom: 20, display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
              <div className="avatar" style={{ width: 56, height: 56, fontSize: 24 }}>{p.user.name.slice(0, 1).toUpperCase()}</div>
              <div className="grow" style={{ flex: 1, minWidth: 220 }}>
                {editing ? (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <input aria-label="Display name" value={name} maxLength={120} onChange={e => setName(e.target.value)} />
                    <button className="btn btn-sm btn-primary" onClick={() => void save()}>Save</button>
                    <button className="btn btn-sm" onClick={() => { setEditing(false); setErr(null); }}>Cancel</button>
                  </div>
                ) : <h2 style={{ margin: 0 }}>{p.user.name}</h2>}
                {err && <p className="muted tiny" style={{ color: "var(--danger)" }} role="alert">{err}</p>}
                <p className="muted" style={{ margin: "4px 0 0" }}>{p.user.email} · {p.user.role === "staff" ? "Staff" : "Member"} · joined {fmtDateTime(p.user.member_since).split(",").slice(0, 2).join(",")}</p>
              </div>
              {!editing && <button className="btn btn-sm" onClick={() => { setName(user?.name ?? p.user.name); setEditing(true); }}>Edit name</button>}
            </div>

            <div className="stats">
              <div className="stat"><div className="k">Lost reports</div><div className="v">{p.lost.total}</div><div className="s">{p.lost.active} active · {p.lost.recovered} recovered</div></div>
              <div className="stat green"><div className="k">Found reports</div><div className="v">{p.found.total}</div><div className="s">{p.found.returned} returned · {p.found.with_staff} with staff</div></div>
              <div className="stat"><div className="k">Matches for you</div><div className="v">{p.matches.total}</div><div className="s">{p.matches.strong} strong · best {p.matches.best_score === null ? "—" : p.matches.best_score.toFixed(2)}</div></div>
              <div className="stat green"><div className="k">Claims</div><div className="v">{p.claims.total}</div><div className="s">{st.length ? st.map(([s, n]) => `${n} ${statusChip(s).text.toLowerCase()}`).join(" · ") : "none yet"}</div></div>
              <div className="stat"><div className="k">Recovery rate</div><div className="v">{p.recovery_rate === null ? "—" : `${pct(p.recovery_rate)}%`}</div><div className="s">of your lost reports</div></div>
              <div className="stat green"><div className="k">Avg time to recover</div><div className="v">{hrs(p.avg_hours_to_recover)}</div><div className="s">claim to handover</div></div>
              <div className="stat"><div className="k">Unread alerts</div><div className="v">{p.unread_notifications}</div><div className="s"><Link to="/dashboard?tab=notifications">Open notifications</Link></div></div>
            </div>

            <div className="charts">
              <div className="card chart"><h3>What you report most</h3>
                {p.categories.length === 0 ? <p className="muted">Nothing reported yet.</p> :
                  <div className="bars">{p.categories.map(c => (
                    <div className="sig" key={c.category} style={{ gridTemplateColumns: "130px 1fr 30px" }}><span>{c.category}</span>
                      <div className="bar"><i style={{ width: `${(c.count / max) * 100}%` }} /></div><span>{c.count}</span></div>))}</div>}</div>
              <div className="card chart"><h3>Your recent activity</h3>
                {p.timeline.length === 0 ? <Empty title="No activity yet." /> : p.timeline.map((t, i) => (
                  <div className="item" key={i} style={{ padding: "6px 0", display: "flex", gap: 10, alignItems: "baseline" }}>
                    <span className="dot" style={{ color: KIND_COLOR[t.kind] }} />
                    <div className="grow" style={{ flex: 1 }}><b>{t.title}</b><div className="muted tiny">{t.detail}</div></div>
                    <span className="muted tiny">{fmtDateTime(t.at)}</span></div>))}</div>
            </div>
          </>);
      }}</Async>
    </>
  );
}
