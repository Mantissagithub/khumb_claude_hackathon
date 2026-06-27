/** Minimal CSV parsing + typed loaders matching the real data/data headers.
 *
 * Loaders return (lng, lat) per AGENTS.md ordering. A hand-rolled parser keeps
 * the dep count down; it handles quoted fields with embedded commas (one row in
 * Chokepoints_Parking.csv has a stray quoted comma).
 */

/** Parse CSV text into rows of {header: value}. RFC-ish: handles "quoted" fields. */
export function parseCSV(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else inQuotes = false;
      } else field += c;
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) return [];
  const header = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => {
    const o: Record<string, string> = {};
    header.forEach((h, i) => (o[h] = (r[i] ?? "").trim()));
    return o;
  });
}

export interface GeoPoint {
  name: string;
  lng: number;
  lat: number;
  category?: string;
}

const num = (v: string) => Number(v);
const ok = (p: GeoPoint) => Number.isFinite(p.lng) && Number.isFinite(p.lat);

export function loadChokepoints(text: string): GeoPoint[] {
  return parseCSV(text)
    .map((r) => ({
      name: r["location_name"],
      category: r["category"],
      lng: num(r["longitude"]),
      lat: num(r["latitude"]),
    }))
    .filter(ok);
}

export function loadPolice(text: string): GeoPoint[] {
  return parseCSV(text)
    .map((r) => ({ name: r["station_name"], lng: num(r["longitude"]), lat: num(r["latitude"]) }))
    .filter(ok);
}

export function loadZones(text: string): GeoPoint[] {
  return parseCSV(text)
    .map((r) => ({ name: r["zone_name"], lng: num(r["centroid_lng"]), lat: num(r["centroid_lat"]) }))
    .filter(ok);
}

export function loadCameras(text: string): GeoPoint[] {
  return parseCSV(text)
    .map((r) => ({ name: r["camera_id"], lng: num(r["longitude"]), lat: num(r["latitude"]) }))
    .filter(ok);
}

/** Aggregate missing-person rows by last_seen_location -> a count prior. */
export function loadMissingPrior(text: string): Map<string, number> {
  const counts = new Map<string, number>();
  for (const r of parseCSV(text)) {
    const loc = (r["last_seen_location"] || "").trim();
    if (loc) counts.set(loc, (counts.get(loc) ?? 0) + 1);
  }
  return counts;
}

export interface DataLayers {
  chokepoints: GeoPoint[];
  police: GeoPoint[];
  zones: GeoPoint[];
  cameras: GeoPoint[];
  missingPrior: Map<string, number>;
}

/** Fetch the bundled default CSVs from /public/data (first paint, pre-upload). */
export async function loadDefaults(): Promise<DataLayers> {
  const get = (f: string) => fetch(`${import.meta.env.BASE_URL}data/${f}`).then((r) => r.text());
  const [cp, pol, zon, cam, mis] = await Promise.all([
    get("Chokepoints_Parking.csv"),
    get("Police_Stations.csv"),
    get("Zone_Boundaries.csv"),
    get("CCTV_Locations.csv"),
    get("Synthetic_Missing_Persons_2500.csv"),
  ]);
  return {
    chokepoints: loadChokepoints(cp),
    police: loadPolice(pol),
    zones: loadZones(zon),
    cameras: loadCameras(cam),
    missingPrior: loadMissingPrior(mis),
  };
}

/** Detect which dataset an uploaded CSV is, by header signature. */
export type CsvKind = "chokepoints" | "police" | "zones" | "cameras" | "missing" | "unknown";

export function detectKind(text: string): CsvKind {
  const first = text.slice(0, text.indexOf("\n")).toLowerCase();
  if (first.includes("location_name") && first.includes("category")) return "chokepoints";
  if (first.includes("station_name")) return "police";
  if (first.includes("zone_name") && first.includes("centroid")) return "zones";
  if (first.includes("camera_id")) return "cameras";
  if (first.includes("last_seen_location") || first.includes("missing_person")) return "missing";
  return "unknown";
}

/** Pick the corridor anchor from chokepoints: prefer Ramkund / no-vehicle
 * pressure zones (the ghat-access danger points), else the first traffic choke. */
export function pickAnchor(chokepoints: GeoPoint[]): GeoPoint | null {
  const byName = chokepoints.find((c) => /ramkund/i.test(c.name));
  if (byName) return byName;
  const pressure = chokepoints.find((c) => /no-vehicle pressure/i.test(c.category ?? ""));
  if (pressure) return pressure;
  const choke = chokepoints.find((c) => /choke/i.test(c.category ?? ""));
  return choke ?? chokepoints[0] ?? null;
}
