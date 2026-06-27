/** Social Force Model constants + agent type table — ported from
 * `sim/engine/params.py` and `sim/agents/types.py`. Constants kept identical so
 * the web variant reproduces the same crush dynamics as the Python model.
 */

// Helbing, Farkas & Vicsek (Nature 2000) canonical values.
export interface SFMParams {
  A: number; // social repulsion strength (N)
  B: number; // social repulsion range (m)
  k: number; // body-force (compression) stiffness (kg/s^2)
  kappa: number; // sliding-friction coefficient (kg/(m·s))
  tau: number; // acceleration relaxation time (s)
  rCut: number; // neighbour interaction cutoff (m)
  vMaxFactor: number; // speed clamp as a multiple of desired speed
  panicSpeedBoost: number; // panic=1 multiplies desired speed by (1+this)
}

export const SFM: SFMParams = {
  A: 2000.0,
  B: 0.08,
  k: 1.2e5,
  kappa: 2.4e5,
  tau: 0.5,
  rCut: 2.0,
  vMaxFactor: 1.3,
  panicSpeedBoost: 1.0,
};

// Family-cohesion + separation config (from SimConfig in simulation.py).
export interface SimConfig {
  dt: number;
  comfortDist: number;
  waitDist: number;
  breakDist: number;
  kCohesion: number;
  fCohesionMax: number;
  lostSpeedFactor: number;
  crushCount: number;
  hardBreakDist: number;
  spawnBandDepth: number;
  spawnMinGap: number;
}

export const SIM_CFG: SimConfig = {
  dt: 0.02,
  comfortDist: 1.0,
  waitDist: 2.5,
  breakDist: 4.0,
  kCohesion: 350.0,
  fCohesionMax: 1500.0,
  lostSpeedFactor: 0.45,
  crushCount: 8,
  hardBreakDist: 12.0,
  spawnBandDepth: 5.0,
  spawnMinGap: 0.7,
};

// Agent types (Helbing-style speeds; masses/radii from pedestrian-dynamics lit).
export interface AgentParams {
  name: string;
  v0: number; // desired free-flow walking speed (m/s)
  mass: number; // kg
  radius: number; // m torso radius
  fallRisk: number; // relative trample susceptibility (0..1)
}

export const AGENT_PARAMS: AgentParams[] = [
  { name: "adult_normal", v0: 1.3, mass: 70.0, radius: 0.25, fallRisk: 0.15 },
  { name: "child", v0: 0.9, mass: 25.0, radius: 0.18, fallRisk: 0.85 },
  { name: "elderly", v0: 0.8, mass: 60.0, radius: 0.25, fallRisk: 0.75 },
  { name: "mobility_impaired", v0: 0.5, mass: 80.0, radius: 0.35, fallRisk: 0.9 },
];

export const TYPE_IDS: Record<string, number> = Object.fromEntries(
  AGENT_PARAMS.map((p, i) => [p.name, i]),
);

export const V0 = AGENT_PARAMS.map((p) => p.v0);
export const MASS = AGENT_PARAMS.map((p) => p.mass);
export const RADIUS = AGENT_PARAMS.map((p) => p.radius);
export const FALL_RISK = AGENT_PARAMS.map((p) => p.fallRisk);

// Colour per type for rendering (adult, child, elderly, mobility-impaired).
export const TYPE_COLORS = ["#7dd3fc", "#fbbf24", "#c084fc", "#fb7185"];
