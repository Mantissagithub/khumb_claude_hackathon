import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import { Loader2 } from "lucide-react";
import { PageHeader } from "@/shared/components/PageHeader";
import { Card } from "@/shared/ui/card";
import { casePoints } from "@/shared/authApi";
import geo from "@/admin/data/geo.json";

const KUMBH_CENTER = [19.99, 73.79]; // Nashik / Trimbak Kumbh area

// status -> heat intensity weight
const WEIGHT = { Active: 1.0, Matched: 0.6, Reunited: 0.35 };

const OVERLAYS = [
  { id: "heat", label: "People density", color: "#aa2d00", on: true },
  { id: "cctv", label: `CCTV (${geo.cctv.length})`, color: "#254fad", on: false },
  { id: "police", label: `Police (${geo.police.length})`, color: "#0a2e0e", on: true },
  { id: "chokepoints", label: `Chokepoints (${geo.chokepoints.length})`, color: "#d9a441", on: true },
  { id: "zones", label: `Zones (${geo.zones.length})`, color: "#181d26", on: false },
];
const STATUS = ["All", "Active", "Matched", "Reunited"];

export default function MapView() {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({});
  const ptsRef = useRef([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("All");
  const [vis, setVis] = useState(Object.fromEntries(OVERLAYS.map((o) => [o.id, o.on])));

  // init map + static overlays once
  useEffect(() => {
    if (mapRef.current || !elRef.current) return;
    const map = L.map(elRef.current, { center: KUMBH_CENTER, zoom: 13, scrollWheelZoom: true });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap", maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;

    const dot = (lat, lng, color, r, label) =>
      L.circleMarker([lat, lng], { radius: r, color, weight: 1, fillColor: color, fillOpacity: 0.7 })
        .bindTooltip(label, { direction: "top" });

    layersRef.current.cctv = L.layerGroup(geo.cctv.map(([la, ln, id]) => dot(la, ln, "#254fad", 2, `CCTV ${id}`)));
    layersRef.current.police = L.layerGroup(geo.police.map(([la, ln, n]) => dot(la, ln, "#0a2e0e", 6, `🚓 ${n}`)));
    layersRef.current.chokepoints = L.layerGroup(geo.chokepoints.map(([la, ln, n, cat]) => dot(la, ln, "#d9a441", 5, `${n} — ${cat}`)));
    layersRef.current.zones = L.layerGroup(geo.zones.map(([la, ln, n]) =>
      L.marker([la, ln], { opacity: 0 }).bindTooltip(n, { permanent: true, direction: "center", className: "zone-label" })
    ));

    // apply initial visibility for static layers
    for (const o of OVERLAYS) if (o.id !== "heat" && vis[o.id]) layersRef.current[o.id].addTo(map);

    casePoints()
      .then((rows) => { ptsRef.current = rows; })
      .catch(() => { ptsRef.current = []; })
      .finally(() => setLoading(false));

    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // (re)build heat layer when data, status filter, or heat toggle changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    if (layersRef.current.heat) { map.removeLayer(layersRef.current.heat); layersRef.current.heat = null; }
    if (!vis.heat) return;
    const pts = ptsRef.current
      .filter((r) => status === "All" || r.status === status)
      .map((r) => [r.lat, r.lng, WEIGHT[r.status] ?? 0.5]);
    layersRef.current.heat = L.heatLayer(pts, { radius: 22, blur: 18, maxZoom: 17, minOpacity: 0.25 }).addTo(map);
  }, [loading, status, vis.heat]);

  // toggle static overlays
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const id of ["cctv", "police", "chokepoints", "zones"]) {
      const layer = layersRef.current[id];
      if (!layer) continue;
      if (vis[id] && !map.hasLayer(layer)) layer.addTo(map);
      if (!vis[id] && map.hasLayer(layer)) map.removeLayer(layer);
    }
  }, [vis]);

  const filteredCount = ptsRef.current.filter((r) => status === "All" || r.status === status).length;

  return (
    <>
      <PageHeader
        title="Map"
        description="Live density of reported cases across the Kumbh, with cameras, police and chokepoints."
      />

      <div className="relative">
        <div ref={elRef} className="h-[calc(100svh-220px)] min-h-[460px] w-full overflow-hidden rounded-lg border border-border" />
        {loading && (
          <div className="absolute inset-0 z-[500] grid place-items-center bg-background/40">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* control panel */}
        <Card className="absolute right-3 top-3 z-[500] w-56 gap-0 border-border bg-card/95 p-3 shadow-lg backdrop-blur">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Heatmap status</p>
          <div className="mb-3 flex flex-wrap gap-1">
            {STATUS.map((s) => (
              <button key={s} onClick={() => setStatus(s)}
                className={`rounded-full px-2.5 py-1 text-xs transition-colors ${
                  status === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"
                }`}>
                {s}
              </button>
            ))}
          </div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Layers</p>
          <div className="space-y-1.5">
            {OVERLAYS.map((o) => (
              <label key={o.id} className="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" checked={!!vis[o.id]}
                  onChange={(e) => setVis((v) => ({ ...v, [o.id]: e.target.checked }))}
                  className="accent-[var(--color-sig-navy,#181d26)]" />
                <span className="size-2.5 rounded-full" style={{ background: o.color }} />
                {o.label}
              </label>
            ))}
          </div>
          <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
            {filteredCount.toLocaleString()} cases shown
          </p>
        </Card>
      </div>
    </>
  );
}
