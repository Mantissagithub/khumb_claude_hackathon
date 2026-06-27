/** Pilgrim roster + family structure — ported from `sim/agents/types.py`
 * (generate_party) and the placement logic in simulation.py (_place_party).
 *
 * The web variant is a fixed-population recirculating model: we build a roster of
 * families ONCE (packed contiguously so a guardian can respawn its whole family
 * by index range on the GPU), and lay them out across the corridor for a lively
 * t=0. Family structure (guardianIdx, famStart, famCount) is immutable; the GPU
 * only mutates position/velocity/lost and re-stages families at the entrance.
 */

import { Corridor } from "./corridor";
import { TYPE_IDS } from "./params";

interface MemberSpec {
  type: string;
  isGuardian: boolean;
}

// Party templates (weight, members) — verbatim from _PARTY_TEMPLATES.
const PARTY_TEMPLATES: Array<[number, MemberSpec[]]> = [
  [0.3, [{ type: "adult_normal", isGuardian: true }]],
  [0.22, [{ type: "adult_normal", isGuardian: true }, { type: "child", isGuardian: false }]],
  [
    0.14,
    [
      { type: "adult_normal", isGuardian: true },
      { type: "child", isGuardian: false },
      { type: "child", isGuardian: false },
    ],
  ],
  [0.12, [{ type: "elderly", isGuardian: true }, { type: "elderly", isGuardian: false }]],
  [0.1, [{ type: "adult_normal", isGuardian: true }, { type: "elderly", isGuardian: false }]],
  [
    0.07,
    [
      { type: "adult_normal", isGuardian: true },
      { type: "elderly", isGuardian: false },
      { type: "child", isGuardian: false },
    ],
  ],
  [0.05, [{ type: "mobility_impaired", isGuardian: true }]],
];

const WEIGHT_SUM = PARTY_TEMPLATES.reduce((s, [w]) => s + w, 0);

/** Deterministic PRNG (mulberry32) so a given seed reproduces a roster. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pickTemplate(rng: () => number): MemberSpec[] {
  let r = rng() * WEIGHT_SUM;
  for (const [w, members] of PARTY_TEMPLATES) {
    if (r < w) return members;
    r -= w;
  }
  return PARTY_TEMPLATES[0][1];
}

export interface Roster {
  count: number;
  typeId: Int32Array;
  isGuardian: Uint32Array; // 1 if guardian/solo
  guardianIdx: Int32Array; // global index of this family's guardian
  famStart: Int32Array; // first index of the family block
  famCount: Int32Array; // members in the family block
  px: Float32Array;
  py: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
}

/** Build a fixed roster of ~`capacity` agents packed by family, laid out across
 * the whole corridor for an immediately-populated scene. */
export function buildRoster(cor: Corridor, capacity: number, seed = 0): Roster {
  const rng = mulberry32(seed);
  const typeId: number[] = [];
  const isGuardian: number[] = [];
  const guardianIdx: number[] = [];
  const famStart: number[] = [];
  const famCount: number[] = [];
  const px: number[] = [];
  const py: number[] = [];

  while (typeId.length < capacity) {
    const members = pickTemplate(rng);
    const start = typeId.length;
    const gIdx = start; // guardian is always the first member of the block
    // Family cluster centre somewhere along the corridor (lively at t=0).
    const cy = cor.yMin + 1 + rng() * (cor.cfg.lengthM - 2);
    const halfW = cor.widthAt(cy) / 2 - 0.4;
    const cx = (rng() * 2 - 1) * Math.max(halfW, 0.1);
    for (let m = 0; m < members.length; m++) {
      const spec = members[m];
      typeId.push(TYPE_IDS[spec.type]);
      isGuardian.push(spec.isGuardian ? 1 : 0);
      guardianIdx.push(gIdx);
      famStart.push(start);
      famCount.push(members.length);
      // Cluster members near the family centre.
      const ox = m === 0 ? 0 : (rng() * 2 - 1) * 1.2;
      const oy = m === 0 ? 0 : (rng() * 2 - 1) * 1.2;
      const x = Math.min(Math.max(cx + ox, -halfW), halfW);
      const y = Math.min(Math.max(cy + oy, cor.yMin + 0.5), cor.yMax - 0.5);
      px.push(x);
      py.push(y);
    }
    // patch famCount for the whole block (already pushed per member above)
  }

  const count = typeId.length;
  return {
    count,
    typeId: Int32Array.from(typeId),
    isGuardian: Uint32Array.from(isGuardian),
    guardianIdx: Int32Array.from(guardianIdx),
    famStart: Int32Array.from(famStart),
    famCount: Int32Array.from(famCount),
    px: Float32Array.from(px),
    py: Float32Array.from(py),
    vx: new Float32Array(count),
    vy: new Float32Array(count).fill(-0.2),
  };
}
