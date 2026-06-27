/** Geographic <-> local-metric projection.
 *
 * Direct port of `shared/geo.py` (LocalProjection): a local equirectangular
 * projection anchored at a reference (lng, lat). Over a corridor a few hundred
 * metres across the distortion is sub-metre — well below the ~0.25 m agent
 * radius. Convention: geographic coords are (lng, lat); metric coords are
 * (x = east, y = north) in metres relative to the anchor.
 */

const M_PER_DEG_LAT = 111_320.0;

export class LocalProjection {
  readonly anchorLng: number;
  readonly anchorLat: number;
  private readonly mPerDegLng: number;

  constructor(anchorLng: number, anchorLat: number) {
    this.anchorLng = anchorLng;
    this.anchorLat = anchorLat;
    this.mPerDegLng = M_PER_DEG_LAT * Math.cos((anchorLat * Math.PI) / 180);
  }

  /** (lng, lat) degrees -> (x, y) metres east/north of the anchor. */
  toXY(lng: number, lat: number): [number, number] {
    return [(lng - this.anchorLng) * this.mPerDegLng, (lat - this.anchorLat) * M_PER_DEG_LAT];
  }

  /** (x, y) metres -> (lng, lat) degrees. */
  toLngLat(x: number, y: number): [number, number] {
    return [this.anchorLng + x / this.mPerDegLng, this.anchorLat + y / M_PER_DEG_LAT];
  }
}

/** Great-circle distance in metres between two (lng, lat) points (haversine). */
export function haversineM(lng1: number, lat1: number, lng2: number, lat2: number): number {
  const r = 6_371_000.0;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlmb = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dphi / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}
