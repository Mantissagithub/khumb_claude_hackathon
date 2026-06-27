/** SimEngine — owns the WebGPU device, buffers, pipelines, and the per-frame
 * compute loop that runs the SFM kernel (sfm.wgsl). Decoupled from React; the
 * useWebGPUSim hook wraps it for component lifecycle.
 *
 * Per frame: clearGrid -> binAgents -> step -> stage, ping-ponging the two state
 * buffers, then reads back positions / lost / density / separations for render
 * and hotspot accumulation.
 */

import shaderSrc from "./webgpu/sfm.wgsl?raw";
import { Corridor } from "./corridor";
import { NavField } from "./navfield";
import { Roster } from "./spawn";
import { SFM, SIM_CFG } from "./params";

export const MAX_PER_CELL = 96;
export const SEP_CAP = 4096;
export const MAX_POLICE = 16;
const WG = 64;

export interface PoliceUnit {
  x: number;
  y: number;
  radius: number;
  strength: number;
}

export interface FrameData {
  count: number;
  state: Float32Array; // capacity*4 (px,py,vx,vy)
  lost: Uint32Array; // capacity
  typeId: Int32Array; // capacity (static)
  density: Uint32Array; // corridorCells
  cnx: number;
  cny: number;
}

export interface SepEvent {
  x: number;
  y: number;
  memberType: number;
  cause: number; // 1 crush, 2 guardian_left
}

export interface EngineControls {
  activeCount: number;
  panicOn: boolean;
  panicX: number;
  panicY: number;
  panicRadius: number;
  paused: boolean;
}

export class SimEngine {
  readonly device: GPUDevice;
  private corridor!: Corridor;
  private roster!: Roster;
  private capacity = 0;
  private gx = 0;
  private gy = 0;
  private numCells = 0;
  private corridorCells = 0;

  private params!: ArrayBuffer;
  private pf!: Float32Array;
  private pi!: Int32Array;
  private pu!: Uint32Array;

  private uniformBuf!: GPUBuffer;
  private policeBuf!: GPUBuffer;
  private policeData = new ArrayBuffer(16 + MAX_POLICE * 16); // count + pad, then vec4[16]
  private stateA!: GPUBuffer;
  private stateB!: GPUBuffer;
  private metaBuf!: GPUBuffer;
  private lostBuf!: GPUBuffer;
  private navBuf!: GPUBuffer;
  private atomicsBuf!: GPUBuffer;
  private bucketBuf!: GPUBuffer;
  private sepBuf!: GPUBuffer;

  private stateRB!: GPUBuffer;
  private lostRB!: GPUBuffer;
  private atomicsRB!: GPUBuffer;
  private sepRB!: GPUBuffer;

  private bindA!: GPUBindGroup; // in=A out=B
  private bindB!: GPUBindGroup; // in=B out=A
  private pClear!: GPUComputePipeline;
  private pBin!: GPUComputePipeline;
  private pStep!: GPUComputePipeline;
  private pStage!: GPUComputePipeline;

  private frame = 0;
  private running = false;
  private rafId = 0;

  controls: EngineControls = {
    activeCount: 0,
    panicOn: false,
    panicX: 0,
    panicY: 0,
    panicRadius: 6,
    paused: false,
  };

  onFrame: ((d: FrameData) => void) | null = null;
  onSeparations: ((e: SepEvent[]) => void) | null = null;

  constructor(device: GPUDevice) {
    this.device = device;
  }

  /** (Re)initialise all GPU resources for a corridor + navfield + roster. Called
   * on first load and on every CSV re-anchor. */
  init(corridor: Corridor, nav: NavField, roster: Roster, initialActive: number): void {
    this.destroyBuffers();
    this.corridor = corridor;
    this.roster = roster;
    this.capacity = roster.count;
    const dev = this.device;

    const gridCs = SFM.rCut;
    this.gx = Math.ceil((corridor.xMax - corridor.xMin) / gridCs);
    this.gy = Math.ceil((corridor.yMax - corridor.yMin) / gridCs);
    this.numCells = this.gx * this.gy;
    this.corridorCells = corridor.nx * corridor.ny;
    this.controls.activeCount = Math.min(initialActive, this.capacity);

    // --- params uniform ---
    this.params = new ArrayBuffer(192);
    this.pf = new Float32Array(this.params);
    this.pi = new Int32Array(this.params);
    this.pu = new Uint32Array(this.params);
    this.uniformBuf = dev.createBuffer({
      size: 192,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    this.policeBuf = dev.createBuffer({
      size: this.policeData.byteLength,
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    new Int32Array(this.policeData)[0] = 0;
    dev.queue.writeBuffer(this.policeBuf, 0, this.policeData);

    // --- state (ping-pong), packed vec4 (px,py,vx,vy) ---
    const stateInit = new Float32Array(this.capacity * 4);
    for (let i = 0; i < this.capacity; i++) {
      const o = i * 4;
      if (i < this.controls.activeCount) {
        stateInit[o] = roster.px[i];
        stateInit[o + 1] = roster.py[i];
        stateInit[o + 2] = roster.vx[i];
        stateInit[o + 3] = roster.vy[i];
      } else {
        stateInit[o] = 1e5 + 10; // parked off-screen
        stateInit[o + 1] = 1e5 + 10;
      }
    }
    const stateUsage =
      GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
    this.stateA = this.makeBuffer(stateInit, stateUsage);
    this.stateB = this.makeBuffer(stateInit, stateUsage);

    // --- meta vec4<i32> (typeId, guardianIdx, famStart, famCount) ---
    const meta = new Int32Array(this.capacity * 4);
    for (let i = 0; i < this.capacity; i++) {
      const o = i * 4;
      meta[o] = roster.typeId[i];
      meta[o + 1] = roster.guardianIdx[i];
      meta[o + 2] = roster.famStart[i];
      meta[o + 3] = roster.famCount[i];
    }
    this.metaBuf = this.makeBuffer(meta, GPUBufferUsage.STORAGE);

    this.lostBuf = this.makeBuffer(
      new Uint32Array(this.capacity),
      GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
    );

    // --- navfield flat f32, 5 per corridor cell ---
    const navFlat = new Float32Array(this.corridorCells * 5);
    for (let c = 0; c < this.corridorCells; c++) {
      const b = c * 5;
      navFlat[b] = nav.eSinkX[c];
      navFlat[b + 1] = nav.eSinkY[c];
      navFlat[b + 2] = nav.distToWall[c];
      navFlat[b + 3] = nav.nWallX[c];
      navFlat[b + 4] = nav.nWallY[c];
    }
    this.navBuf = this.makeBuffer(navFlat, GPUBufferUsage.STORAGE);

    this.atomicsBuf = dev.createBuffer({
      size: (this.numCells + this.corridorCells) * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });
    this.bucketBuf = dev.createBuffer({
      size: this.numCells * MAX_PER_CELL * 4,
      usage: GPUBufferUsage.STORAGE,
    });
    this.sepBuf = dev.createBuffer({
      size: (1 + SEP_CAP * 4) * 4,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });

    // --- readback buffers ---
    const rb = (size: number) =>
      dev.createBuffer({ size, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
    this.stateRB = rb(this.capacity * 4 * 4);
    this.lostRB = rb(this.capacity * 4);
    this.atomicsRB = rb((this.numCells + this.corridorCells) * 4);
    this.sepRB = rb((1 + SEP_CAP * 4) * 4);

    this.buildPipelines();
    this.writeParams();
  }

  private makeBuffer(data: Float32Array | Int32Array | Uint32Array, usage: number): GPUBuffer {
    const buf = this.device.createBuffer({
      size: data.byteLength,
      usage,
      mappedAtCreation: true,
    });
    new (data.constructor as { new (b: ArrayBuffer): typeof data })(buf.getMappedRange()).set(
      data as never,
    );
    buf.unmap();
    return buf;
  }

  private buildPipelines(): void {
    const dev = this.device;
    const module = dev.createShaderModule({ code: shaderSrc });
    const storage = (rw: boolean): GPUBufferBindingLayout => ({
      type: rw ? "storage" : "read-only-storage",
    });
    const layout = dev.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: "uniform" } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: storage(false) },
        { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: storage(true) },
        { binding: 3, visibility: GPUShaderStage.COMPUTE, buffer: storage(false) },
        { binding: 4, visibility: GPUShaderStage.COMPUTE, buffer: storage(true) },
        { binding: 5, visibility: GPUShaderStage.COMPUTE, buffer: storage(false) },
        { binding: 6, visibility: GPUShaderStage.COMPUTE, buffer: storage(true) },
        { binding: 7, visibility: GPUShaderStage.COMPUTE, buffer: storage(true) },
        { binding: 8, visibility: GPUShaderStage.COMPUTE, buffer: storage(true) },
        { binding: 9, visibility: GPUShaderStage.COMPUTE, buffer: { type: "uniform" } },
      ],
    });
    const pipelineLayout = dev.createPipelineLayout({ bindGroupLayouts: [layout] });
    const mk = (entryPoint: string) =>
      dev.createComputePipeline({ layout: pipelineLayout, compute: { module, entryPoint } });
    this.pClear = mk("clearGrid");
    this.pBin = mk("binAgents");
    this.pStep = mk("step");
    this.pStage = mk("stage");

    const entries = (inBuf: GPUBuffer, outBuf: GPUBuffer): GPUBindGroupEntry[] => [
      { binding: 0, resource: { buffer: this.uniformBuf } },
      { binding: 1, resource: { buffer: inBuf } },
      { binding: 2, resource: { buffer: outBuf } },
      { binding: 3, resource: { buffer: this.metaBuf } },
      { binding: 4, resource: { buffer: this.lostBuf } },
      { binding: 5, resource: { buffer: this.navBuf } },
      { binding: 6, resource: { buffer: this.atomicsBuf } },
      { binding: 7, resource: { buffer: this.bucketBuf } },
      { binding: 8, resource: { buffer: this.sepBuf } },
      { binding: 9, resource: { buffer: this.policeBuf } },
    ];
    this.bindA = dev.createBindGroup({ layout, entries: entries(this.stateA, this.stateB) });
    this.bindB = dev.createBindGroup({ layout, entries: entries(this.stateB, this.stateA) });
  }

  private writeParams(): void {
    const c = this.corridor;
    const f = this.pf;
    const ii = this.pi;
    const u = this.pu;
    f[0] = SFM.A; f[1] = SFM.B; f[2] = SFM.k; f[3] = SFM.kappa;
    f[4] = SFM.tau; f[5] = SFM.rCut; f[6] = SFM.vMaxFactor; f[7] = SFM.panicSpeedBoost;
    f[8] = SIM_CFG.comfortDist; f[9] = SIM_CFG.breakDist; f[10] = SIM_CFG.hardBreakDist;
    f[11] = SIM_CFG.kCohesion;
    f[12] = SIM_CFG.fCohesionMax; f[13] = SIM_CFG.lostSpeedFactor; f[14] = SIM_CFG.dt;
    f[15] = SIM_CFG.spawnBandDepth;
    ii[16] = SIM_CFG.crushCount; ii[17] = this.controls.activeCount; ii[18] = this.capacity;
    u[19] = this.frame >>> 0;
    ii[20] = this.gx; ii[21] = this.gy; ii[22] = MAX_PER_CELL; ii[23] = this.numCells;
    ii[24] = c.nx; ii[25] = c.ny; ii[26] = SEP_CAP; ii[27] = this.corridorCells;
    f[28] = c.xMin; f[29] = c.yMin; f[30] = c.xMax; f[31] = c.yMax;
    f[32] = c.cellM; f[33] = SFM.rCut; f[34] = c.yMin + c.cellM; f[35] = SIM_CFG.waitDist;
    f[36] = c.entranceY; f[37] = c.cfg.wideWidthM / 2 - 0.4;
    f[38] = c.cfg.wideWidthM; f[39] = c.cfg.narrowWidthM;
    f[40] = c.cfg.throatLenM; f[41] = c.cfg.lengthM;
    f[42] = this.controls.panicX; f[43] = this.controls.panicY;
    f[44] = this.controls.panicRadius; f[45] = this.controls.panicOn ? 1 : 0;
    this.device.queue.writeBuffer(this.uniformBuf, 0, this.params);
  }

  setActiveCount(n: number): void {
    this.controls.activeCount = Math.max(0, Math.min(Math.round(n), this.capacity));
  }
  setPanic(on: boolean, x = 0, y = 0): void {
    this.controls.panicOn = on;
    this.controls.panicX = x;
    this.controls.panicY = y;
  }

  /** Install police units (metric coords) as lateral repellers. */
  setDeployment(units: PoliceUnit[]): void {
    const n = Math.min(units.length, MAX_POLICE);
    new Int32Array(this.policeData)[0] = n;
    const f = new Float32Array(this.policeData, 16);
    for (let i = 0; i < n; i++) {
      f[i * 4] = units[i].x;
      f[i * 4 + 1] = units[i].y;
      f[i * 4 + 2] = units[i].radius;
      f[i * 4 + 3] = units[i].strength;
    }
    this.device.queue.writeBuffer(this.policeBuf, 0, this.policeData);
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

  /** Advance exactly one frame (used by the step button while paused). */
  async stepOnce(): Promise<void> {
    await this.tick();
  }

  private loop = (): void => {
    if (!this.running) return;
    this.tick().then(() => {
      if (this.running) this.rafId = requestAnimationFrame(this.loop);
    });
  };

  private async tick(): Promise<void> {
    this.writeParams();
    const dev = this.device;
    const inIsA = this.frame % 2 === 0;
    const bind = inIsA ? this.bindA : this.bindB;
    const outBuf = inIsA ? this.stateB : this.stateA;

    const enc = dev.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setBindGroup(0, bind);
    const dispatch = (p: GPUComputePipeline, n: number) => {
      pass.setPipeline(p);
      pass.dispatchWorkgroups(Math.ceil(n / WG));
    };
    dispatch(this.pClear, this.numCells + this.corridorCells);
    dispatch(this.pBin, this.capacity);
    dispatch(this.pStep, this.capacity);
    dispatch(this.pStage, this.capacity);
    pass.end();

    enc.copyBufferToBuffer(outBuf, 0, this.stateRB, 0, this.capacity * 16);
    enc.copyBufferToBuffer(this.lostBuf, 0, this.lostRB, 0, this.capacity * 4);
    enc.copyBufferToBuffer(
      this.atomicsBuf,
      0,
      this.atomicsRB,
      0,
      (this.numCells + this.corridorCells) * 4,
    );
    enc.copyBufferToBuffer(this.sepBuf, 0, this.sepRB, 0, (1 + SEP_CAP * 4) * 4);
    dev.queue.submit([enc.finish()]);

    await Promise.all([
      this.stateRB.mapAsync(GPUMapMode.READ),
      this.lostRB.mapAsync(GPUMapMode.READ),
      this.atomicsRB.mapAsync(GPUMapMode.READ),
      this.sepRB.mapAsync(GPUMapMode.READ),
    ]);

    const state = new Float32Array(this.stateRB.getMappedRange().slice(0));
    const lost = new Uint32Array(this.lostRB.getMappedRange().slice(0));
    const atomics = new Uint32Array(this.atomicsRB.getMappedRange().slice(0));
    const sepBytes = this.sepRB.getMappedRange().slice(0);
    this.stateRB.unmap();
    this.lostRB.unmap();
    this.atomicsRB.unmap();
    this.sepRB.unmap();

    if (this.onFrame) {
      this.onFrame({
        count: this.capacity,
        state,
        lost,
        typeId: this.roster.typeId,
        density: atomics.subarray(this.numCells, this.numCells + this.corridorCells),
        cnx: this.corridor.nx,
        cny: this.corridor.ny,
      });
    }
    if (this.onSeparations) {
      const u = new Uint32Array(sepBytes);
      const fv = new Float32Array(sepBytes);
      const n = Math.min(u[0], SEP_CAP);
      if (n > 0) {
        const events: SepEvent[] = [];
        for (let e = 0; e < n; e++) {
          const b = 1 + e * 4;
          events.push({ x: fv[b], y: fv[b + 1], memberType: fv[b + 2] | 0, cause: fv[b + 3] });
        }
        this.onSeparations(events);
      }
    }
    this.frame++;
  }

  private destroyBuffers(): void {
    for (const b of [
      this.uniformBuf, this.policeBuf, this.stateA, this.stateB, this.metaBuf, this.lostBuf,
      this.navBuf, this.atomicsBuf, this.bucketBuf, this.sepBuf, this.stateRB, this.lostRB,
      this.atomicsRB, this.sepRB,
    ]) {
      b?.destroy?.();
    }
  }

  destroy(): void {
    this.pause();
    this.destroyBuffers();
  }
}
