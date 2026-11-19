import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Icon } from "./Icon";

export interface Place { address: string; latitude: number | null; longitude: number | null }

interface Hit { display_name: string; lat: string; lon: string }

/**
 * Free location input (no API key): OpenStreetMap tiles via Leaflet, place search via Nominatim
 * (only when the user presses Search, as its usage policy requires), the browser's geolocation, or a
 * click on the map. Works without coordinates too: the typed place name alone is still saved.
 */
export function LocationPicker({ value, onChange, label }: { value: Place; onChange: (p: Place) => void; label: string }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const cb = useRef(onChange); cb.current = onChange;
  const addr = useRef(value.address); addr.current = value.address;

  const put = (lat: number, lon: number, address?: string, zoom?: number) => {
    cb.current({ address: address ?? addr.current, latitude: +lat.toFixed(6), longitude: +lon.toFixed(6) });
    map.current?.setView([lat, lon], zoom ?? Math.max(map.current.getZoom(), 16));
  };

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { center: [20, 0], zoom: 2, scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "© OpenStreetMap contributors",
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => put(e.latlng.lat, e.latlng.lng));
    map.current = m;
    return () => { m.remove(); map.current = null; marker.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (value.latitude === null || value.longitude === null) { marker.current?.remove(); marker.current = null; return; }
    const ll: L.LatLngExpression = [value.latitude, value.longitude];
    if (!marker.current) marker.current = L.circleMarker(ll, { radius: 9, color: "#2152d4", weight: 3, fillColor: "#3b73f0", fillOpacity: .85 }).addTo(m);
    else marker.current.setLatLng(ll);
  }, [value.latitude, value.longitude]);

  async function search() {
    if (!query.trim()) return;
    setBusy(true); setNote(""); setHits([]);
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`);
      if (!r.ok) throw new Error();
      const data = (await r.json()) as Hit[];
      setHits(data);
      if (!data.length) setNote("No places found. Try a more general name, or click the map.");
    } catch { setNote("Place search is unavailable right now. Click the map or type the place name."); }
    finally { setBusy(false); }
  }

  function locate() {
    if (!navigator.geolocation) { setNote("Your browser does not support location."); return; }
    setNote("Finding your location…");
    navigator.geolocation.getCurrentPosition(
      p => { setNote(""); put(p.coords.latitude, p.coords.longitude, value.address || "My current location"); },
      () => setNote("Could not get your location (permission denied or unavailable). Click the map instead."),
      { enableHighAccuracy: true, timeout: 10_000 });
  }

  return (
    <div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label>Search for a place
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Building, street, landmark…"
                   onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); void search(); } }} />
          </label>
        </div>
        <button type="button" className="btn" onClick={() => void search()} disabled={busy}><Icon name="search" size={15} />Search</button>
        <button type="button" className="btn" onClick={locate} aria-label="Use my current location"><Icon name="locate" size={15} />My location</button>
      </div>
      {hits.length > 0 && (
        <ul className="card" style={{ listStyle: "none", margin: "8px 0 0", padding: 4 }}>
          {hits.map(h => (
            <li key={h.display_name + h.lat}><button type="button" className="btn btn-ghost btn-block" style={{ justifyContent: "flex-start", textAlign: "left" }}
              onClick={() => { put(+h.lat, +h.lon, h.display_name.split(",").slice(0, 3).join(",").trim(), 17); setHits([]); }}>
              <Icon name="pin" size={15} />{h.display_name}</button></li>))}
        </ul>)}
      {note && <p className="muted tiny" role="status" style={{ marginTop: 6 }}>{note}</p>}
      <div ref={el} className="map" role="application" aria-label={`${label} map`} />
      <p className="hint">Click the map to drop a pin. Coordinates help the matcher compare distances; they are optional.</p>
      <div className="grid2" style={{ marginTop: 8 }}>
        <label>Place name / details
          <input value={value.address} placeholder="e.g. 2nd floor reading room"
                 onChange={e => onChange({ ...value, address: e.target.value })} />
        </label>
        <label>Coordinates
          <input readOnly value={value.latitude !== null && value.longitude !== null ? `${value.latitude}, ${value.longitude}` : "Not set"} />
          {value.latitude !== null && <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 4 }}
            onClick={() => onChange({ ...value, latitude: null, longitude: null })}>Clear pin</button>}
        </label>
      </div>
    </div>
  );
}
