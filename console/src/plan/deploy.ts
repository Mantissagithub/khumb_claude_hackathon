/** Deployment planning (Pillar B, live variant).
 *
 * Accumulates separation events into a coarse hotspot grid in the corridor's
 * metric frame, then greedily places police / help-desk posts to maximise the
 * separation-risk covered within a radius — and reports the coverage metric the
 * console shows ("N forces -> cover X% of risk"). Hotspots and posts are also
 * projected to (lng, lat) for the geo map.
 */

import { Corridor } from "../sim/corridor";
import { haversineM } from "../sim/proj";
import type { GeoPoint } from "../data/csv";
import type { SepEvent } from "../sim/engine";

const HOT_CELL_M = 3.0; // hotspot bin size (m)
const COVER_RADIUS_M = 8.0; // a post covers risk within this radius

export class HotspotAccumulator {
  private cor: Corridor;
  private gx: number;
  private gy: number;
  private grid: Float32Array;
  total = 0;

  constructor(cor: Corridor) {
    this.cor = cor;
    this.gx = Math.ceil((cor.xMax - cor.xMin) / HOT_CELL_M);
    this.gy = Math.ceil((cor.yMax - cor.yMin) / HOT_CELL_M);
    this.grid = new Float32Array(this.gx * this.gy);
  }

  add(events: SepEvent[]): void {
    for (const e of events) {
      const ix = Math.min(Math.max(((e.x - this.cor.xMin) / HOT_CELL_M) | 0, 0), this.gx - 1);
      const iy = Math.min(Math.max(((e.y - this.cor.yMin) / HOT_CELL_M) | 0, 0), this.gy - 1);
      this.grid[iy * this.gx + ix] += 1;
      this.total += 1;
    }
  }

  reset(): void {
    this.grid.fill(0);
    this.total = 0;
  }

  /** Hotspot cells as (x, y, weight) in the metric frame, weight desc. */
  cells(): Array<{ x: number; y: number; w: number }> {
    const out: Array<{ x: number; y: number; w: number }> = [];
    for (let iy = 0; iy < this.gy; iy++) {
      for (let ix = 0; ix < this.gx; ix++) {
        const w = this.grid[iy * this.gx + ix];
        if (w > 0) {
          out.push({
            x: this.cor.xMin + (ix + 0.5) * HOT_CELL_M,
            y: this.cor.yMin + (iy + 0.5) * HOT_CELL_M,
            w,
          });
        }
      }
    }
    return out.sort((a, b) => b.w - a.w);
  }

  /** Hotspots projected to (lng, lat) for the geo map. */
  hotspotsLngLat(minWeight = 1): Array<{ lng: number; lat: number; w: number }> {
    return this.cells()
      .filter((c) => c.w >= minWeight)
      .map((c) => {
        const [lng, lat] = this.cor.proj.toLngLat(c.x, c.y);
        return { lng, lat, w: c.w };
      });
  }
}

export interface DeployPost {
  lng: number;
  lat: number;
  covered: number; // risk weight this post covers
  station?: string; // nearest real police station, if any
}

export interface DeployPlan {
  posts: DeployPost[];
  coveredPct: number;
  totalEvents: number;
  uniformPct: number; // baseline: same #posts spread evenly along the corridor
}

/** Greedily choose up to `nPosts` post locations over the hotspot grid, then
 * snap each to the nearest provided police station (if any) for dispatch. */
export function planDeployment(
  acc: HotspotAccumulator,
  cor: Corridor,
  police: GeoPoint[],
  nPosts = 3,
): DeployPlan {
  const cells = acc.cells();
  const total = acc.total;
  if (total < 5) return { posts: [], coveredPct: 0, totalEvents: total, uniformPct: 0 };

  const remaining = cells.map((c) => ({ ...c }));
  const posts: DeployPost[] = [];
  for (let k = 0; k < nPosts; k++) {
    let best: { x: number; y: number } | null = null;
    let bestW = 0;
    for (const a of remaining) {
      if (a.w <= 0) continue;
      let w = 0;
      for (const b of remaining)
        if (Math.hypot(a.x - b.x, a.y - b.y) <= COVER_RADIUS_M) w += b.w;
      if (w > bestW) {
        bestW = w;
        best = { x: a.x, y: a.y };
      }
    }
    if (!best || bestW <= 0) break;
    for (const b of remaining)
      if (Math.hypot(best.x - b.x, best.y - b.y) <= COVER_RADIUS_M) b.w = 0;
    const [lng, lat] = cor.proj.toLngLat(best.x, best.y);
    let station: string | undefined;
    if (police.length) {
      let nearest = police[0];
      let nd = Infinity;
      for (const p of police) {
        const d = haversineM(lng, lat, p.lng, p.lat);
        if (d < nd) {
          nd = d;
          nearest = p;
        }
      }
      station = nearest.name;
    }
    posts.push({ lng, lat, covered: bestW, station });
  }
  const covered = posts.reduce((s, p) => s + p.covered, 0);

  // Baseline: nPosts spread evenly down the corridor centre-line.
  let uniformCovered = 0;
  const seen = new Set<number>();
  for (let k = 0; k < nPosts; k++) {
    const uy = cor.yMin + ((k + 0.5) / nPosts) * (cor.yMax - cor.yMin);
    for (let ci = 0; ci < cells.length; ci++) {
      if (seen.has(ci)) continue;
      if (Math.hypot(0 - cells[ci].x, uy - cells[ci].y) <= COVER_RADIUS_M) {
        uniformCovered += cells[ci].w;
        seen.add(ci);
      }
    }
  }

  return {
    posts,
    coveredPct: total ? Math.round((covered / total) * 100) : 0,
    totalEvents: total,
    uniformPct: total ? Math.round((uniformCovered / total) * 100) : 0,
  };
}
