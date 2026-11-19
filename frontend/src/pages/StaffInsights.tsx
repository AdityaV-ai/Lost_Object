import { useEffect } from "react";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { Async, Empty, useAsync } from "../components/States";
import { fmtDateTime } from "../utils";

const ago = (h: number) => (h < 1 ? "under 1 h" : h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} d`);
const KIND_COLOR: Record<string, string> = { lost: "var(--primary)", found: "var(--success)", claim: "var(--warning, #b7791f)", staff: "var(--muted)" };

/** Re-run a query on an interval while the tab is open, so figures stay current without a page reload. */
function useLive(reload: () => void, ms = 30000) {
  useEffect(() => { const id = setInterval(reload, ms); return () => clearInterval(id); }, [reload, ms]);
}

export function ActivityTab() {
  const q = useAsync(() => api.staff.activity(60), []);
  useLive(q.reload);
  return (
    <Async q={q} empty={d => d.length ? null : <Empty title="Nothing has happened yet." />}>{rows => (
      <>
        <p className="muted tiny" style={{ marginBottom: 12 }}><span style={{ color: "var(--success)" }}>●</span> Live feed of reports, claims and staff actions · newest first · refreshes every 30 s</p>
        {rows.map((a, i) => (
          <div className="card item" key={i}><span className="dot" style={{ color: KIND_COLOR[a.kind] }} />
            <div className="grow"><b>{a.title}</b> <span className="mono tiny">{a.code}</span>
              <div className="muted tiny">{a.detail ? `${a.detail} · ` : ""}{a.actor}</div></div>
            <span className="muted tiny">{fmtDateTime(a.at)}</span></div>))}
      </>)}</Async>
  );
}

export function HotspotsTab() {
  const q = useAsync(api.staff.hotspots, []);
  return (
    <Async q={q} empty={d => d.length ? null : <Empty title="No locations recorded yet." />}>{rows => {
      const max = Math.max(1, ...rows.map(r => r.total));
      return (
        <div className="card chart"><h3>Where items go missing and get found</h3>
          <div className="table-wrap"><table>
            <thead><tr><th>Place</th><th>Lost</th><th>Found</th><th>Returned</th><th style={{ width: "30%" }}>Share</th><th /></tr></thead>
            <tbody>{rows.map(r => (
              <tr key={r.place}><td><b>{r.place}</b></td><td>{r.lost}</td><td>{r.found}</td><td>{r.recovered}</td>
                <td><div className="bar"><i style={{ width: `${(r.total / max) * 100}%` }} /></div></td>
                <td>{r.map_url ? <a href={r.map_url} target="_blank" rel="noreferrer"><Icon name="pin" size={14} /> Map</a> : <span className="muted tiny">no coordinates</span>}</td></tr>))}</tbody>
          </table></div>
          <p className="muted tiny" style={{ marginTop: 8 }}>Grouped by the place name people entered. Map links use the average of the reported coordinates.</p>
        </div>);
    }}</Async>
  );
}

export function AttentionTab() {
  const q = useAsync(api.staff.attention, []);
  useLive(q.reload);
  return (
    <Async q={q}>{d => (
      <>
        <div className="stats" style={{ marginBottom: 16 }}>
          <div className="stat red"><div className="k">High</div><div className="v">{d.counts.high ?? 0}</div><div className="s">claims waiting over {d.rules.claim_waiting_h} h</div></div>
          <div className="stat"><div className="k">Medium</div><div className="v">{d.counts.medium ?? 0}</div><div className="s">stalled evidence, collection, deposits</div></div>
          <div className="stat green"><div className="k">Low</div><div className="v">{d.counts.low ?? 0}</div><div className="s">no match or unclaimed items</div></div>
        </div>
        {d.items.length === 0 ? <Empty title="Nothing needs attention right now." /> : d.items.map((i, k) => (
          <div className="card item" key={k}>
            <span className="dot" style={{ color: i.severity === "high" ? "var(--danger)" : i.severity === "medium" ? "var(--primary)" : "var(--success)" }} />
            <div className="grow"><b>{i.title}</b> <span className="mono tiny">{i.code}</span>
              <div className="muted tiny">{i.detail} · {i.severity} priority</div></div>
            <span className="muted tiny">{ago(i.age_hours)}</span></div>))}
        <p className="muted tiny" style={{ marginTop: 10 }}>Rules: claim unreviewed {d.rules.claim_waiting_h} h · evidence unanswered {d.rules.evidence_waiting_h} h · approved item uncollected {d.rules.collection_waiting_h} h · found item unclaimed {Math.round(d.rules.unclaimed_found_h / 24)} d.</p>
      </>)}</Async>
  );
}

export function CommunityTab() {
  const q = useAsync(api.staff.community, []);
  return (
    <Async q={q}>{d => (
      <>
        <div className="stats" style={{ marginBottom: 16 }}>
          <div className="stat"><div className="k">Members</div><div className="v">{d.members}</div><div className="s">registered accounts</div></div>
          <div className="stat green"><div className="k">Items returned</div><div className="v">{d.returned_total}</div><div className="s">found items back with their owners</div></div>
        </div>
        <div className="charts">
          <div className="card chart"><h3>Top finders</h3>
            {d.top_finders.length === 0 ? <p className="muted">No found items yet.</p> :
              <table><thead><tr><th>Name</th><th>Reported</th><th>Returned</th></tr></thead>
                <tbody>{d.top_finders.map(f => <tr key={f.name}><td>{f.name}</td><td>{f.reported}</td><td>{f.returned}</td></tr>)}</tbody></table>}</div>
          <div className="card chart"><h3>Top reporters (lost items)</h3>
            {d.top_owners.length === 0 ? <p className="muted">No lost reports yet.</p> :
              <table><thead><tr><th>Name</th><th>Reported</th><th>Recovered</th></tr></thead>
                <tbody>{d.top_owners.map(f => <tr key={f.name}><td>{f.name}</td><td>{f.reported}</td><td>{f.recovered}</td></tr>)}</tbody></table>}</div>
        </div>
      </>)}</Async>
  );
}
