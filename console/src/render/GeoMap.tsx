/** Real-geography map (react-leaflet): uploaded markers, accumulated separation
 * hotspots, and the suggested police deployment — all in (lng, lat). Updates as
 * CSVs are uploaded and as the sim accumulates risk.
 */

import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";
import type { DataLayers } from "../data/csv";
import type { DeployPlan } from "../plan/deploy";

interface Props {
  layers: DataLayers;
  hotspots: Array<{ lng: number; lat: number; w: number }>;
  plan: DeployPlan;
  center: [number, number]; // [lat, lng]
  deployed?: Array<{ lng: number; lat: number; radiusM: number }>;
}

function Recenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true });
  }, [center, map]);
  return null;
}

const dot = (color: string, fillOpacity = 0.9) => ({
  color,
  weight: 1,
  fillColor: color,
  fillOpacity,
});

export default function GeoMap({ layers, hotspots, plan, center, deployed = [] }: Props) {
  return (
    <MapContainer center={center} zoom={14} zoomControl={false} attributionControl={false} style={{ height: "100%", width: "100%" }}>
      <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
      <Recenter center={center} />

      {/* CCTV — faint coverage dots */}
      {layers.cameras.map((c, i) => (
        <CircleMarker key={`cam${i}`} center={[c.lat, c.lng]} radius={2} pathOptions={dot("#2c3e58", 0.5)} />
      ))}
      {/* Zones — centroids */}
      {layers.zones.map((z, i) => (
        <CircleMarker key={`z${i}`} center={[z.lat, z.lng]} radius={3} pathOptions={dot("#6b7c93", 0.3)}>
          <Tooltip>{z.name}</Tooltip>
        </CircleMarker>
      ))}
      {/* Chokepoints — geography that drives the sim */}
      {layers.chokepoints.map((c, i) => (
        <CircleMarker key={`cp${i}`} center={[c.lat, c.lng]} radius={4} pathOptions={dot("#38bdf8", 0.8)}>
          <Tooltip>{c.name} · {c.category}</Tooltip>
        </CircleMarker>
      ))}
      {/* Separation hotspots */}
      {hotspots.map((h, i) => (
        <CircleMarker
          key={`h${i}`}
          center={[h.lat, h.lng]}
          radius={Math.min(6 + h.w, 22)}
          pathOptions={{ color: "#ff3b30", weight: 0, fillColor: "#ff3b30", fillOpacity: 0.5 }}
        />
      ))}
      {/* Police stations */}
      {layers.police.map((p, i) => (
        <CircleMarker key={`p${i}`} center={[p.lat, p.lng]} radius={4} pathOptions={dot("#a3b6cc", 0.7)}>
          <Tooltip>{p.name}</Tooltip>
        </CircleMarker>
      ))}
      {/* Suggested deployment posts */}
      {plan.posts.map((p, i) => (
        <CircleMarker key={`dep${i}`} center={[p.lat, p.lng]} radius={8} pathOptions={dot("#34d399", 0.95)}>
          <Tooltip>Deploy here{p.station ? ` · dispatch ${p.station}` : ""}</Tooltip>
        </CircleMarker>
      ))}
      {/* Deployed officers */}
      {deployed.map((d, i) => (
        <CircleMarker
          key={`officer${i}`}
          center={[d.lat, d.lng]}
          radius={9}
          pathOptions={{ color: "#34d399", weight: 2, fillColor: "#13283a", fillOpacity: 0.9 }}
        >
          <Tooltip>Officer deployed</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
