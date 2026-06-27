/** Parametric corridor domain anchored to real geography.
 *
 * Port of `sim/geometry/corridor.py`. The meter-scale shape is an explicit
 * model: a length, a width profile that narrows to a throat near the ghat, and a
 * cell-grid walkable mask. The anchor is real (from data/data); the throat
 * geometry is the modelled part. Default = the Ramkund ghat approach (site of the
 * 2003 stampede, 39 dead in a narrow approach).
 *
 * Local metric frame: origin = ghat water edge (sink); +y away from ghat toward
 * entrance; +x lateral. Grid arrays indexed [iy*nx + ix].
 */

import { LocalProjection } from "./proj";

export interface CorridorConfig {
  corridorId: string;
  anchorLng: number;
  anchorLat: number;
  lengthM: number; // ghat -> entrance extent
  wideWidthM: number; // width at the plaza/entrance end
  narrowWidthM: number; // width at the throat near the ghat
  throatLenM: number; // length of the narrow throat from the ghat
  cellM: number; // grid resolution (m)
  bearingDeg: number; // compass bearing of approach axis (for export)
}

// Real Ramkund / Godavari ghat access point (Chokepoints_Parking.csv).
export const RAMKUND: CorridorConfig = {
  corridorId: "ramkund",
  anchorLng: 73.79062,
  anchorLat: 20.0067,
  lengthM: 60.0,
  wideWidthM: 28.0,
  narrowWidthM: 6.0,
  throatLenM: 14.0,
  cellM: 0.5,
  bearingDeg: 20.0,
};

export class Corridor {
  readonly cfg: CorridorConfig;
  readonly proj: LocalProjection;
  readonly cellM: number;
  readonly xMin: number;
  readonly xMax: number;
  readonly yMin: number;
  readonly yMax: number;
  readonly nx: number;
  readonly ny: number;
  readonly xs: Float32Array; // cell-center x (length nx)
  readonly ys: Float32Array; // cell-center y (length ny)
  readonly walkable: Uint8Array; // [ny*nx] 1/0
  readonly sinkMask: Uint8Array; // [ny*nx] 1/0 (ghat water edge, bottom row)
  readonly entranceY: number;

  constructor(cfg: CorridorConfig) {
    this.cfg = cfg;
    this.proj = new LocalProjection(cfg.anchorLng, cfg.anchorLat);
    const c = cfg.cellM;
    this.cellM = c;
    this.xMin = -cfg.wideWidthM / 2;
    this.xMax = +cfg.wideWidthM / 2;
    this.yMin = 0;
    this.yMax = cfg.lengthM;
    this.nx = Math.ceil((this.xMax - this.xMin) / c);
    this.ny = Math.ceil((this.yMax - this.yMin) / c);

    this.xs = new Float32Array(this.nx);
    for (let i = 0; i < this.nx; i++) this.xs[i] = this.xMin + (i + 0.5) * c;
    this.ys = new Float32Array(this.ny);
    for (let i = 0; i < this.ny; i++) this.ys[i] = this.yMin + (i + 0.5) * c;

    this.walkable = new Uint8Array(this.nx * this.ny);
    for (let iy = 0; iy < this.ny; iy++) {
      const halfW = this.widthAt(this.ys[iy]) / 2;
      for (let ix = 0; ix < this.nx; ix++) {
        this.walkable[iy * this.nx + ix] = Math.abs(this.xs[ix]) <= halfW ? 1 : 0;
      }
    }
    // Ghat water edge: bottom row of walkable cells (y ~ 0).
    this.sinkMask = new Uint8Array(this.nx * this.ny);
    for (let ix = 0; ix < this.nx; ix++) this.sinkMask[ix] = this.walkable[ix];

    this.entranceY = this.yMax - c;
  }

  /** Corridor width (m) at distance y from the ghat. Narrow through the throat,
   * then opens linearly to wideWidthM at the plaza end. */
  widthAt(y: number): number {
    const cfg = this.cfg;
    const span = Math.max(cfg.lengthM - cfg.throatLenM, 1e-6);
    const frac = Math.min(Math.max((y - cfg.throatLenM) / span, 0), 1);
    return cfg.narrowWidthM + (cfg.wideWidthM - cfg.narrowWidthM) * frac;
  }
}
