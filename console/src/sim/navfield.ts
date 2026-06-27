/** Navigation + wall fields over a Corridor — the browser replacement for
 * `sim/geometry/navfield.py` (which uses scikit-fmm).
 *
 * The grid is small (~56×120), so we solve both fields on the CPU once per
 * corridor change:
 *   distToSink  geodesic distance to the ghat over walkable 8-neighbours
 *               (multi-source Dijkstra) -> -gradient -> desired heading eSink.
 *   distToWall  distance to the nearest non-walkable cell (Dijkstra over all
 *               cells from wall sources) -> gradient -> inward normal nWall.
 *
 * Outputs match build_navfield's arrays and are uploaded to the GPU as storage.
 */

import { Corridor } from "./corridor";

export interface NavField {
  nx: number;
  ny: number;
  distToSink: Float32Array;
  eSinkX: Float32Array;
  eSinkY: Float32Array;
  distToWall: Float32Array;
  nWallX: Float32Array;
  nWallY: Float32Array;
}

const SQRT2 = Math.SQRT2;
// 8-neighbour offsets with euclidean step lengths.
const NB = [
  [-1, 0, 1],
  [1, 0, 1],
  [0, -1, 1],
  [0, 1, 1],
  [-1, -1, SQRT2],
  [-1, 1, SQRT2],
  [1, -1, SQRT2],
  [1, 1, SQRT2],
] as const;

/** Minimal binary-heap Dijkstra over the grid.
 * `passable(idx)` gates which cells may be entered. Edge cost = step * cellM. */
function dijkstra(
  nx: number,
  ny: number,
  cellM: number,
  sources: number[],
  passable: (idx: number) => boolean,
): Float32Array {
  const n = nx * ny;
  const dist = new Float32Array(n).fill(Infinity);
  // Heap of [dist, idx]; tiny enough that a flat array + sift is plenty fast.
  const heap: Array<[number, number]> = [];
  const push = (d: number, i: number) => {
    heap.push([d, i]);
    let c = heap.length - 1;
    while (c > 0) {
      const p = (c - 1) >> 1;
      if (heap[p][0] <= heap[c][0]) break;
      [heap[p], heap[c]] = [heap[c], heap[p]];
      c = p;
    }
  };
  const pop = (): [number, number] => {
    const top = heap[0];
    const last = heap.pop()!;
    if (heap.length) {
      heap[0] = last;
      let c = 0;
      for (;;) {
        const l = 2 * c + 1;
        const r = l + 1;
        let s = c;
        if (l < heap.length && heap[l][0] < heap[s][0]) s = l;
        if (r < heap.length && heap[r][0] < heap[s][0]) s = r;
        if (s === c) break;
        [heap[s], heap[c]] = [heap[c], heap[s]];
        c = s;
      }
    }
    return top;
  };

  for (const s of sources) {
    dist[s] = 0;
    push(0, s);
  }
  while (heap.length) {
    const [d, idx] = pop();
    if (d > dist[idx]) continue;
    const ix = idx % nx;
    const iy = (idx / nx) | 0;
    for (const [dx, dy, step] of NB) {
      const jx = ix + dx;
      const jy = iy + dy;
      if (jx < 0 || jx >= nx || jy < 0 || jy >= ny) continue;
      const j = jy * nx + jx;
      if (!passable(j)) continue;
      const nd = d + step * cellM;
      if (nd < dist[j]) {
        dist[j] = nd;
        push(nd, j);
      }
    }
  }
  return dist;
}

/** Central-difference gradient (spacing cellM), one-sided at edges. Mirrors
 * numpy.gradient over a finite field. Returns [gx, gy]. */
function gradient(
  f: Float32Array,
  nx: number,
  ny: number,
  cellM: number,
): [Float32Array, Float32Array] {
  const gx = new Float32Array(nx * ny);
  const gy = new Float32Array(nx * ny);
  for (let iy = 0; iy < ny; iy++) {
    for (let ix = 0; ix < nx; ix++) {
      const i = iy * nx + ix;
      // d/dx
      if (ix === 0) gx[i] = (f[i + 1] - f[i]) / cellM;
      else if (ix === nx - 1) gx[i] = (f[i] - f[i - 1]) / cellM;
      else gx[i] = (f[i + 1] - f[i - 1]) / (2 * cellM);
      // d/dy
      if (iy === 0) gy[i] = (f[i + nx] - f[i]) / cellM;
      else if (iy === ny - 1) gy[i] = (f[i] - f[i - nx]) / cellM;
      else gy[i] = (f[i + nx] - f[i - nx]) / (2 * cellM);
    }
  }
  return [gx, gy];
}

export function buildNavField(cor: Corridor): NavField {
  const { nx, ny, cellM, walkable, sinkMask } = cor;
  const n = nx * ny;

  // --- geodesic distance to the ghat sink, routed around walls ---
  const sinkSources: number[] = [];
  for (let i = 0; i < n; i++) if (sinkMask[i]) sinkSources.push(i);
  const distToSink = dijkstra(nx, ny, cellM, sinkSources, (i) => walkable[i] === 1);

  // Desired direction = -grad(distToSink). Compute on a finite copy (inf -> a
  // value just past the max), trust only on walkable cells.
  let maxFinite = 0;
  for (let i = 0; i < n; i++)
    if (isFinite(distToSink[i]) && distToSink[i] > maxFinite) maxFinite = distToSink[i];
  const finite = new Float32Array(n);
  for (let i = 0; i < n; i++)
    finite[i] = isFinite(distToSink[i]) ? distToSink[i] : maxFinite + 10 * cellM;
  const [gx, gy] = gradient(finite, nx, ny, cellM);
  const eSinkX = new Float32Array(n);
  const eSinkY = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    if (!walkable[i]) continue;
    let ex = -gx[i];
    let ey = -gy[i];
    const norm = Math.hypot(ex, ey) || 1;
    eSinkX[i] = ex / norm;
    eSinkY[i] = ey / norm;
  }

  // --- distance to nearest wall + inward normal ---
  // Sources = non-walkable cells (dist 0); propagate through all cells.
  const wallSources: number[] = [];
  for (let i = 0; i < n; i++) if (!walkable[i]) wallSources.push(i);
  const rawWall = dijkstra(nx, ny, cellM, wallSources, () => true);
  const distToWall = new Float32Array(n);
  for (let i = 0; i < n; i++)
    distToWall[i] = walkable[i] ? (isFinite(rawWall[i]) ? rawWall[i] : 0) : 0;
  // Inward normal = normalized gradient of the wall-distance field (points away
  // from the nearest wall, toward the interior).
  const [wx, wy] = gradient(rawWall, nx, ny, cellM);
  const nWallX = new Float32Array(n);
  const nWallY = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    if (!walkable[i]) continue;
    const norm = Math.hypot(wx[i], wy[i]) || 1;
    nWallX[i] = wx[i] / norm;
    nWallY[i] = wy[i] / norm;
  }

  return { nx, ny, distToSink, eSinkX, eSinkY, distToWall, nWallX, nWallY };
}
