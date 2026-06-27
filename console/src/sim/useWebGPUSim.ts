/** React glue around SimEngine (WebGPU) / CpuSim (fallback).
 *
 * Owns the corridor + navfield + roster lifecycle, re-anchoring when a
 * Chokepoints CSV is uploaded, and surfaces a per-frame ref (for the canvas) plus
 * throttled stats + a deployment plan (for the panels). Per-frame data is kept in
 * a ref so the 60 fps loop never triggers React re-renders.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Corridor, RAMKUND } from "./corridor";
import { buildNavField } from "./navfield";
import { buildRoster } from "./spawn";
import { SimEngine, type FrameData, type SepEvent, type PoliceUnit } from "./engine";
import { initWebGPU } from "./webgpu/device";
import { CpuSim } from "./cpuFallback";
import { HotspotAccumulator, planDeployment, type DeployPlan } from "../plan/deploy";
import type { GeoPoint } from "../data/csv";

const CAPACITY = 6000;
const INITIAL_ACTIVE = 1400;
const SEED = 7;

export interface SimStats {
  activeCount: number;
  peakDensity: number;
  separations: number;
  hotspots: number;
}

interface SimLike {
  init(c: Corridor, nav: ReturnType<typeof buildNavField>, r: ReturnType<typeof buildRoster>, a: number): void;
  start(): void;
  pause(): void;
  isRunning(): boolean;
  stepOnce(): Promise<void>;
  setActiveCount(n: number): void;
  setPanic(on: boolean, x?: number, y?: number): void;
  setDeployment(units: PoliceUnit[]): void;
  destroy(): void;
  controls: { activeCount: number };
  onFrame: ((d: FrameData) => void) | null;
  onSeparations: ((e: SepEvent[]) => void) | null;
}

export interface Ring {
  x: number;
  y: number;
  age: number;
}

export interface UseSim {
  ready: boolean;
  mode: "gpu" | "cpu" | "init";
  adapterInfo: string;
  corridor: Corridor | null;
  frameRef: React.MutableRefObject<FrameData | null>;
  accRef: React.MutableRefObject<HotspotAccumulator | null>;
  ringsRef: React.MutableRefObject<Ring[]>;
  hotspots: Array<{ lng: number; lat: number; w: number }>;
  stats: SimStats;
  plan: DeployPlan;
  running: boolean;
  setSurge: (n: number) => void;
  setPanic: (on: boolean) => void;
  setPanicAt: (x: number, y: number) => void;
  togglePlay: () => void;
  reset: () => void;
  reanchor: (anchorLng: number, anchorLat: number) => void;
  setPolice: (p: GeoPoint[]) => void;
  deployed: Array<{ lng: number; lat: number; radiusM: number }>;
  deployToPlan: () => void;
  clearDeployment: () => void;
  claudeRationale: string;
  claudeSource: string;
  deployPosts: (posts: Array<{ lng: number; lat: number }>) => void;
  applyClaudePlan: (resp: { posts: Array<{ lng: number; lat: number }>; rationale: string; source: string }) => void;
}

// Squad-sized officer presence (sim/controllables/deployment.py POLICE_PARAMS).
const SQUAD = { radius: 5.0, strength: 350.0 };

export function useWebGPUSim(): UseSim {
  const simRef = useRef<SimLike | null>(null);
  const frameRef = useRef<FrameData | null>(null);
  const accRef = useRef<HotspotAccumulator | null>(null);
  const ringsRef = useRef<Ring[]>([]);
  const policeRef = useRef<GeoPoint[]>([]);
  const surgeRef = useRef(INITIAL_ACTIVE);
  const panicOnRef = useRef(false);

  const [mode, setMode] = useState<"gpu" | "cpu" | "init">("init");
  const [adapterInfo, setAdapterInfo] = useState("");
  const [corridor, setCorridor] = useState<Corridor | null>(null);
  const [ready, setReady] = useState(false);
  const [running, setRunning] = useState(false);
  const [stats, setStats] = useState<SimStats>({
    activeCount: 0, peakDensity: 0, separations: 0, hotspots: 0,
  });
  const [plan, setPlan] = useState<DeployPlan>({
    posts: [], coveredPct: 0, totalEvents: 0, uniformPct: 0,
  });
  const [hotspots, setHotspots] = useState<Array<{ lng: number; lat: number; w: number }>>([]);
  const [deployed, setDeployed] = useState<Array<{ lng: number; lat: number; radiusM: number }>>([]);
  const [claudeRationale, setClaudeRationale] = useState("");
  const [claudeSource, setClaudeSource] = useState("");
  const planRef = useRef<DeployPlan>({ posts: [], coveredPct: 0, totalEvents: 0, uniformPct: 0 });

  const rebuild = useCallback((anchorLng: number, anchorLat: number) => {
    const sim = simRef.current;
    if (!sim) return;
    const cor = new Corridor({ ...RAMKUND, anchorLng, anchorLat });
    const nav = buildNavField(cor);
    const roster = buildRoster(cor, CAPACITY, SEED);
    sim.init(cor, nav, roster, surgeRef.current);
    sim.setPanic(panicOnRef.current);
    accRef.current = new HotspotAccumulator(cor);
    sim.onFrame = (d) => {
      frameRef.current = d;
    };
    sim.onSeparations = (e) => {
      accRef.current?.add(e);
      const rings = ringsRef.current;
      for (const ev of e) rings.push({ x: ev.x, y: ev.y, age: 0 });
      if (rings.length > 200) rings.splice(0, rings.length - 200);
    };
    setCorridor(cor);
    if (!sim.isRunning()) {
      sim.start();
      setRunning(true);
    }
  }, []);

  // boot: pick GPU or CPU, build the default Ramkund corridor.
  useEffect(() => {
    let disposed = false;
    (async () => {
      const gpu = await initWebGPU();
      if (disposed) return;
      if (gpu) {
        simRef.current = new SimEngine(gpu.device) as unknown as SimLike;
        setMode("gpu");
        setAdapterInfo(gpu.adapterInfo);
      } else {
        simRef.current = new CpuSim() as unknown as SimLike;
        setMode("cpu");
        setAdapterInfo("CPU fallback (WebGPU unavailable)");
      }
      rebuild(RAMKUND.anchorLng, RAMKUND.anchorLat);
      setReady(true);
    })();
    return () => {
      disposed = true;
      simRef.current?.destroy();
    };
  }, [rebuild]);

  // throttled stats + plan recompute (~4 Hz) — keeps React renders cheap.
  useEffect(() => {
    const id = setInterval(() => {
      const f = frameRef.current;
      const acc = accRef.current;
      const cor = corridor;
      if (!f || !acc || !cor) return;
      // peak density over the corridor cells (persons / m^2)
      let peak = 0;
      const area = cor.cellM * cor.cellM;
      for (let i = 0; i < f.density.length; i++) {
        const d = f.density[i] / area;
        if (d > peak) peak = d;
      }
      const hotspots = acc.cells().filter((c) => c.w >= 2).length;
      setStats({
        activeCount: simRef.current?.controls.activeCount ?? 0,
        peakDensity: peak,
        separations: acc.total,
        hotspots,
      });
      const p = planDeployment(acc, cor, policeRef.current, 3);
      planRef.current = p;
      setPlan(p);
      setHotspots(acc.hotspotsLngLat(2));
    }, 250);
    return () => clearInterval(id);
  }, [corridor]);

  const setSurge = useCallback((n: number) => {
    surgeRef.current = n;
    simRef.current?.setActiveCount(n);
  }, []);
  const setPanic = useCallback((on: boolean) => {
    panicOnRef.current = on;
    const c = simRef.current?.controls as { panicX?: number; panicY?: number } | undefined;
    simRef.current?.setPanic(on, c?.panicX ?? 0, c?.panicY ?? 0);
  }, []);
  const setPanicAt = useCallback((x: number, y: number) => {
    simRef.current?.setPanic(panicOnRef.current, x, y);
  }, []);
  const togglePlay = useCallback(() => {
    const sim = simRef.current;
    if (!sim) return;
    if (sim.isRunning()) {
      sim.pause();
      setRunning(false);
    } else {
      sim.start();
      setRunning(true);
    }
  }, []);
  const reset = useCallback(() => {
    accRef.current?.reset();
    ringsRef.current = [];
  }, []);
  const clearDeployment = useCallback(() => {
    simRef.current?.setDeployment([]);
    setDeployed([]);
  }, []);
  const reanchor = useCallback(
    (lng: number, lat: number) => {
      accRef.current?.reset();
      ringsRef.current = [];
      clearDeployment();
      rebuild(lng, lat);
    },
    [rebuild, clearDeployment],
  );
  const setPolice = useCallback((p: GeoPoint[]) => {
    policeRef.current = p;
  }, []);
  const deployToPlan = useCallback(() => {
    const cor = corridor;
    const posts = planRef.current.posts;
    if (!cor || !posts.length) return;
    const units: PoliceUnit[] = posts.map((p) => {
      const [x, y] = cor.proj.toXY(p.lng, p.lat);
      return { x, y, radius: SQUAD.radius, strength: SQUAD.strength };
    });
    simRef.current?.setDeployment(units);
    setDeployed(posts.map((p) => ({ lng: p.lng, lat: p.lat, radiusM: SQUAD.radius })));
  }, [corridor]);

  const deployPosts = useCallback((posts: Array<{ lng: number; lat: number }>) => {
    const cor = corridor;
    if (!cor || !posts.length) return;
    const units: PoliceUnit[] = posts.map((p) => {
      const [x, y] = cor.proj.toXY(p.lng, p.lat);
      return { x, y, radius: SQUAD.radius, strength: SQUAD.strength };
    });
    simRef.current?.setDeployment(units);
    setDeployed(posts.map((p) => ({ lng: p.lng, lat: p.lat, radiusM: SQUAD.radius })));
  }, [corridor]);

  const applyClaudePlan = useCallback(
    (resp: { posts: Array<{ lng: number; lat: number }>; rationale: string; source: string }) => {
      deployPosts(resp.posts);
      setClaudeRationale(resp.rationale);
      setClaudeSource(resp.source);
    },
    [deployPosts],
  );

  return {
    ready, mode, adapterInfo, corridor, frameRef, accRef, ringsRef, hotspots,
    stats, plan, running, deployed,
    setSurge, setPanic, setPanicAt, togglePlay, reset, reanchor, setPolice,
    deployToPlan, clearDeployment,
    claudeRationale, claudeSource, deployPosts, applyClaudePlan,
  };
}
