/** CPU fallback when WebGPU is unavailable — the same SFM kernel in a plain JS
 * loop at reduced population, so the demo never hard-fails. Mirrors the math in
 * sfm.wgsl (a faithful, slower twin), capped at ~1500 agents. Emits the same
 * FrameData / SepEvent shapes as SimEngine so renderers don't branch.
 */

import { Corridor } from "./corridor";
import { NavField } from "./navfield";
import { Roster } from "./spawn";
import { SFM, SIM_CFG, V0, MASS, RADIUS } from "./params";
import type { FrameData, SepEvent, EngineControls, PoliceUnit } from "./engine";

export const CPU_CAP = 1500;

export class CpuSim {
  private cor!: Corridor;
  private nav!: NavField;
  private roster!: Roster;
  private cap = 0;
  private px!: Float32Array;
  private py!: Float32Array;
  private vx!: Float32Array;
  private vy!: Float32Array;
  private lost!: Uint32Array;
  private density!: Uint32Array;
  private gx = 0;
  private gy = 0;
  private gridCs = SFM.rCut;
  private police: PoliceUnit[] = [];
  private running = false;
  private rafId = 0;
  private frame = 0;

  controls: EngineControls = {
    activeCount: 0, panicOn: false, panicX: 0, panicY: 0, panicRadius: 6, paused: false,
  };
  onFrame: ((d: FrameData) => void) | null = null;
  onSeparations: ((e: SepEvent[]) => void) | null = null;

  init(corridor: Corridor, nav: NavField, roster: Roster, initialActive: number): void {
    this.cor = corridor;
    this.nav = nav;
    this.cap = Math.min(roster.count, CPU_CAP);
    // Truncate the roster to whole families within the cap.
    let cap = this.cap;
    while (cap > 0 && roster.famStart[cap - 1] + roster.famCount[cap - 1] > this.cap) cap--;
    this.cap = cap;
    this.roster = roster;
    this.px = roster.px.slice(0, this.cap);
    this.py = roster.py.slice(0, this.cap);
    this.vx = roster.vx.slice(0, this.cap);
    this.vy = roster.vy.slice(0, this.cap);
    this.lost = new Uint32Array(this.cap);
    this.gx = Math.ceil((corridor.xMax - corridor.xMin) / this.gridCs);
    this.gy = Math.ceil((corridor.yMax - corridor.yMin) / this.gridCs);
    this.density = new Uint32Array(corridor.nx * corridor.ny);
    this.controls.activeCount = Math.min(initialActive, this.cap);
  }

  setActiveCount(n: number): void {
    this.controls.activeCount = Math.max(0, Math.min(Math.round(n), this.cap));
  }
  setPanic(on: boolean, x = 0, y = 0): void {
    this.controls.panicOn = on;
    this.controls.panicX = x;
    this.controls.panicY = y;
  }
  setDeployment(units: PoliceUnit[]): void {
    this.police = units.slice(0, 16);
  }
  start(): void {
    if (this.running) return;
    this.running = true;
    this.loop();
  }
  pause(): void {
    this.running = false;
    if (this.rafId) cancelAnimationFrame(this.rafId);
  }
  isRunning(): boolean {
    return this.running;
  }
  async stepOnce(): Promise<void> {
    this.tick();
  }
  destroy(): void {
    this.pause();
  }

  private loop = (): void => {
    if (!this.running) return;
    this.tick();
    this.rafId = requestAnimationFrame(this.loop);
  };

  private cidx(x: number, y: number): number {
    const ix = Math.min(Math.max(((x - this.cor.xMin) / this.cor.cellM) | 0, 0), this.cor.nx - 1);
    const iy = Math.min(Math.max(((y - this.cor.yMin) / this.cor.cellM) | 0, 0), this.cor.ny - 1);
    return iy * this.cor.nx + ix;
  }

  private tick(): void {
    const cor = this.cor;
    const nav = this.nav;
    const n = this.controls.activeCount;
    const dt = SIM_CFG.dt;

    // bin into grid
    const head = new Int32Array(this.gx * this.gy).fill(-1);
    const next = new Int32Array(n).fill(-1);
    this.density.fill(0);
    for (let i = 0; i < n; i++) {
      const cx = Math.min(Math.max(((this.px[i] - cor.xMin) / this.gridCs) | 0, 0), this.gx - 1);
      const cy = Math.min(Math.max(((this.py[i] - cor.yMin) / this.gridCs) | 0, 0), this.gy - 1);
      const c = cy * this.gx + cx;
      next[i] = head[c];
      head[c] = i;
      this.density[this.cidx(this.px[i], this.py[i])]++;
    }

    const events: SepEvent[] = [];
    const fx = new Float32Array(n);
    const fy = new Float32Array(n);
    const nearArr = new Int32Array(n);
    const r = this.roster;

    for (let i = 0; i < n; i++) {
      const t = r.typeId[i];
      const ri = RADIUS[t];
      const mass = MASS[t];
      const gIdx = r.guardianIdx[i];
      const amG = gIdx === i;

      let panic = 0;
      if (this.controls.panicOn) {
        const dpx = this.px[i] - this.controls.panicX;
        const dpy = this.py[i] - this.controls.panicY;
        if (dpx * dpx + dpy * dpy < this.controls.panicRadius ** 2) panic = 1;
      }
      let v0 = V0[t];
      if (amG && r.famCount[i] > 1) {
        let slowest = v0;
        let dmax = 0;
        for (let j = r.famStart[i]; j < r.famStart[i] + r.famCount[i]; j++) {
          if (j === i || j >= n) continue;
          if (V0[r.typeId[j]] < slowest) slowest = V0[r.typeId[j]];
          if (!this.lost[j]) {
            const dd = Math.hypot(this.px[j] - this.px[i], this.py[j] - this.py[i]);
            if (dd > dmax) dmax = dd;
          }
        }
        v0 = slowest;
        if (dmax > SIM_CFG.waitDist) v0 = 0.05;
      }
      v0 *= 1 + SFM.panicSpeedBoost * panic;
      if (this.lost[i]) v0 *= SIM_CFG.lostSpeedFactor;

      const dc = this.cidx(this.px[i], this.py[i]);
      let fxi = (mass * (v0 * nav.eSinkX[dc] - this.vx[i])) / SFM.tau;
      let fyi = (mass * (v0 * nav.eSinkY[dc] - this.vy[i])) / SFM.tau;

      const cx = Math.min(Math.max(((this.px[i] - cor.xMin) / this.gridCs) | 0, 0), this.gx - 1);
      const cy = Math.min(Math.max(((this.py[i] - cor.yMin) / this.gridCs) | 0, 0), this.gy - 1);
      let near = 0;
      for (let ncy = cy - 1; ncy <= cy + 1; ncy++) {
        if (ncy < 0 || ncy >= this.gy) continue;
        for (let ncx = cx - 1; ncx <= cx + 1; ncx++) {
          if (ncx < 0 || ncx >= this.gx) continue;
          for (let j = head[ncy * this.gx + ncx]; j !== -1; j = next[j]) {
            if (j === i) continue;
            const dx = this.px[i] - this.px[j];
            const dy = this.py[i] - this.py[j];
            const d = Math.hypot(dx, dy);
            if (d > SFM.rCut || d < 1e-9) continue;
            if (d < 1.0) near++;
            const nx = dx / d;
            const ny = dy / d;
            const overlap = ri + RADIUS[r.typeId[j]] - d;
            let frep = SFM.A * Math.exp(overlap / SFM.B);
            if (overlap > 0) frep += SFM.k * overlap;
            fxi += frep * nx;
            fyi += frep * ny;
            if (overlap > 0) {
              const tx = -ny;
              const ty = nx;
              const dvt = (this.vx[j] - this.vx[i]) * tx + (this.vy[j] - this.vy[i]) * ty;
              const ff = SFM.kappa * overlap * dvt;
              fxi += ff * tx;
              fyi += ff * ty;
            }
          }
        }
      }
      const dw = nav.distToWall[dc];
      if (dw < SFM.rCut) {
        const overlapW = ri - dw;
        let fwall = SFM.A * Math.exp(overlapW / SFM.B);
        if (overlapW > 0) fwall += SFM.k * overlapW;
        fxi += fwall * nav.nWallX[dc];
        fyi += fwall * nav.nWallY[dc];
      }
      // police lateral repulsion (perpendicular to desired heading)
      for (const u of this.police) {
        const dpx = this.px[i] - u.x;
        const dpy = this.py[i] - u.y;
        const dpd = Math.hypot(dpx, dpy);
        if (dpd < u.radius && dpd > 1e-6) {
          const rx = dpx / dpd;
          const ry = dpy / dpd;
          const dot = rx * nav.eSinkX[dc] + ry * nav.eSinkY[dc];
          const lx = rx - dot * nav.eSinkX[dc];
          const ly = ry - dot * nav.eSinkY[dc];
          const ln = Math.hypot(lx, ly);
          if (ln > 1e-6) {
            const mag = (u.strength * Math.exp(-dpd / (0.5 * u.radius))) / ln;
            fxi += mag * lx;
            fyi += mag * ly;
          }
        }
      }
      nearArr[i] = near;
      fx[i] = fxi;
      fy[i] = fyi;
    }

    // cohesion + separation (needs near from the force pass)
    for (let i = 0; i < n; i++) {
      const gIdx = r.guardianIdx[i];
      if (gIdx === i || gIdx < 0 || this.lost[i]) continue;
      const dx = this.px[gIdx] - this.px[i];
      const dy = this.py[gIdx] - this.py[i];
      const d = Math.hypot(dx, dy);
      const inStaging = this.py[i] > cor.yMax - SIM_CFG.spawnBandDepth;
      const crushed = nearArr[i] >= SIM_CFG.crushCount;
      if (d > SIM_CFG.hardBreakDist || (d > SIM_CFG.breakDist && crushed && !inStaging)) {
        this.lost[i] = 1;
        events.push({ x: this.px[i], y: this.py[i], memberType: r.typeId[i], cause: 1 });
      } else if (d > SIM_CFG.comfortDist) {
        const mag = Math.min(SIM_CFG.kCohesion * (d - SIM_CFG.comfortDist), SIM_CFG.fCohesionMax);
        fx[i] += (mag * dx) / d;
        fy[i] += (mag * dy) / d;
      }
    }

    // integrate
    for (let i = 0; i < n; i++) {
      const t = r.typeId[i];
      const mass = MASS[t];
      let nvx = this.vx[i] + (fx[i] / mass) * dt;
      let nvy = this.vy[i] + (fy[i] / mass) * dt;
      const speed = Math.hypot(nvx, nvy);
      const v0c = Math.max(V0[t], 0.3);
      const vcap = Math.min(SFM.vMaxFactor * v0c, 4.0);
      if (speed > vcap) {
        const s = vcap / Math.max(speed, 1e-9);
        nvx *= s;
        nvy *= s;
      }
      this.vx[i] = nvx;
      this.vy[i] = nvy;
      this.px[i] += nvx * dt;
      this.py[i] += nvy * dt;
      // hard containment: keep agents inside the walkable corridor (matches GPU + _clamp_to_walkable)
      this.py[i] = Math.min(Math.max(this.py[i], 0), cor.cfg.lengthM);
      const hw = cor.widthAt(this.py[i]) / 2 - 0.1;
      if (this.px[i] > hw) { this.px[i] = hw; this.vx[i] *= 0.5; }
      else if (this.px[i] < -hw) { this.px[i] = -hw; this.vx[i] *= 0.5; }
    }

    // recirculate: guardian-triggered family re-stage at entrance
    for (let i = 0; i < n; i++) {
      if (r.guardianIdx[i] !== i) continue;
      if (this.py[i] > cor.yMin + cor.cellM) continue;
      const fs = r.famStart[i];
      const fc = r.famCount[i];
      const halfW = cor.cfg.wideWidthM / 2 - 0.4;
      const cxc = (Math.random() * 2 - 1) * halfW;
      const cyc = cor.entranceY - Math.random() * SIM_CFG.spawnBandDepth;
      for (let j = fs; j < fs + fc && j < n; j++) {
        const ox = j === fs ? 0 : (Math.random() * 2 - 1) * 1.2;
        const oy = j === fs ? 0 : (Math.random() * 2 - 1) * 1.2;
        this.px[j] = Math.min(Math.max(cxc + ox, -halfW), halfW);
        this.py[j] = Math.min(Math.max(cyc + oy, cor.yMax - SIM_CFG.spawnBandDepth), cor.yMax - 0.5);
        this.vx[j] = 0;
        this.vy[j] = -0.2;
        this.lost[j] = 0;
      }
    }

    // pack a FrameData (full capacity-shaped state for the renderer)
    const state = new Float32Array(this.cap * 4);
    for (let i = 0; i < this.cap; i++) {
      const o = i * 4;
      if (i < n) {
        state[o] = this.px[i];
        state[o + 1] = this.py[i];
      } else {
        state[o] = 1e5;
        state[o + 1] = 1e5;
      }
    }
    if (this.onFrame) {
      this.onFrame({
        count: this.cap,
        state,
        lost: this.lost,
        typeId: this.roster.typeId.subarray(0, this.cap),
        density: this.density,
        cnx: cor.nx,
        cny: cor.ny,
      });
    }
    if (events.length && this.onSeparations) this.onSeparations(events);
    this.frame++;
  }
}
