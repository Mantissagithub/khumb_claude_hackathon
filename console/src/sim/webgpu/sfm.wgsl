// Social Force Model on the GPU — WGSL port of sim/engine/forces.py +
// the cohesion / separation / spawn logic of sim/engine/simulation.py.
//
// Four compute entry points run per frame:
//   clearGrid  -> zero the neighbour-grid counts, density, and the sep counter
//   binAgents  -> bucket active agents into a uniform grid + accumulate density
//   step       -> SFM forces + family cohesion + separation + integrate
//   stage      -> recirculation: re-stage a family at the entrance when its
//                 guardian reaches the ghat (fixed-population, no compaction)
//
// Buffer packing keeps us within the 8-storage-buffer default limit:
//   stateIn/stateOut : vec4 = (px, py, vx, vy), double-buffered (ping-pong)
//   meta             : vec4<i32> = (typeId, guardianIdx, famStart, famCount)
//   lost             : u32 per agent (1 = separated dependent)
//   nav              : flat f32, 5 per corridor cell (eSinkX,eSinkY,distWall,nWx,nWy)
//   atomics          : [0..numCells) grid counts, then [.. +corridorCells) density
//   bucket           : numCells * maxPerCell agent indices
//   sep              : atomic<u32>; [0]=count, then 4 words per event (bitcast f32)

struct Params {
  A: f32, B: f32, k: f32, kappa: f32,
  tau: f32, rCut: f32, vMaxFactor: f32, panicBoost: f32,
  comfortDist: f32, breakDist: f32, hardBreakDist: f32, kCohesion: f32,
  fCohesionMax: f32, lostSpeedFactor: f32, dt: f32, spawnBandDepth: f32,
  crushCount: i32, activeCount: i32, nAgents: i32, frame: u32,
  gx: i32, gy: i32, maxPerCell: i32, numCells: i32,
  cnx: i32, cny: i32, sepCap: i32, corridorCells: i32,
  xMin: f32, yMin: f32, xMax: f32, yMax: f32,
  cellM: f32, gridCs: f32, sinkThresh: f32, waitDist: f32,
  entranceY: f32, entranceHalfW: f32, wideWidth: f32, narrowWidth: f32,
  throatLen: f32, lengthM: f32, panicX: f32, panicY: f32,
  panicRadius: f32, panicActive: f32, _pad1: f32, _pad2: f32,
};

// Police deployment (ported from sim/controllables/deployment.py): each unit is
// (x, y, control_radius, strength). Within radius it adds a LATERAL repulsion
// (perpendicular to the desired heading) that spreads the crowd sideways and
// lowers density/pressure without ever pushing anyone backward.
struct Police {
  count: i32, _p0: i32, _p1: i32, _p2: i32,
  units: array<vec4<f32>, 16>,
};

@group(0) @binding(0) var<uniform> P: Params;
@group(0) @binding(9) var<uniform> POL: Police;
@group(0) @binding(1) var<storage, read>        stateIn: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read_write>   stateOut: array<vec4<f32>>;
@group(0) @binding(3) var<storage, read>         meta: array<vec4<i32>>;
@group(0) @binding(4) var<storage, read_write>   lost: array<u32>;
@group(0) @binding(5) var<storage, read>         nav: array<f32>;
@group(0) @binding(6) var<storage, read_write>   atomics: array<atomic<u32>>;
@group(0) @binding(7) var<storage, read_write>   bucket: array<u32>;
@group(0) @binding(8) var<storage, read_write>   sep: array<atomic<u32>>;

const SENTINEL: f32 = 1.0e5; // parked agents live beyond this x

fn typeV0(t: i32) -> f32 {
  if (t == 1) { return 0.9; }   // child
  if (t == 2) { return 0.8; }   // elderly
  if (t == 3) { return 0.5; }   // mobility_impaired
  return 1.3;                   // adult_normal
}
fn typeMass(t: i32) -> f32 {
  if (t == 1) { return 25.0; }
  if (t == 2) { return 60.0; }
  if (t == 3) { return 80.0; }
  return 70.0;
}
fn typeRadius(t: i32) -> f32 {
  if (t == 1) { return 0.18; }
  if (t == 2) { return 0.25; }
  if (t == 3) { return 0.35; }
  return 0.25;
}

fn corridorCell(x: f32, y: f32) -> i32 {
  let ix = clamp(i32((x - P.xMin) / P.cellM), 0, P.cnx - 1);
  let iy = clamp(i32((y - P.yMin) / P.cellM), 0, P.cny - 1);
  return iy * P.cnx + ix;
}

fn corHalfW(y: f32) -> f32 {
  let span = max(P.lengthM - P.throatLen, 1e-6);
  let frac = clamp((y - P.throatLen) / span, 0.0, 1.0);
  return 0.5 * (P.narrowWidth + (P.wideWidth - P.narrowWidth) * frac);
}

// hash -> [0,1) for cheap per-agent randomness when staging.
fn rand(seed: u32) -> f32 {
  var s = seed * 747796405u + 2891336453u;
  s = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
  s = (s >> 22u) ^ s;
  return f32(s) / 4294967296.0;
}

fn isActive(i: i32) -> bool { return i < P.activeCount; }
fn isParked(p: vec2<f32>) -> bool { return p.x > SENTINEL; }

// ----------------------------------------------------------------- clearGrid
@compute @workgroup_size(64)
fn clearGrid(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i < P.numCells + P.corridorCells) {
    atomicStore(&atomics[i], 0u);
  }
  if (i == 0) { atomicStore(&sep[0], 0u); }
}

// ----------------------------------------------------------------- binAgents
@compute @workgroup_size(64)
fn binAgents(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= P.nAgents) { return; }
  let s = stateIn[i];
  let p = s.xy;
  if (!isActive(i) || isParked(p)) { return; }

  let cx = clamp(i32((p.x - P.xMin) / P.gridCs), 0, P.gx - 1);
  let cy = clamp(i32((p.y - P.yMin) / P.gridCs), 0, P.gy - 1);
  let cell = cy * P.gx + cx;
  let slot = atomicAdd(&atomics[cell], 1u);
  if (i32(slot) < P.maxPerCell) {
    bucket[cell * P.maxPerCell + i32(slot)] = u32(i);
  }
  // density accumulates over the fine corridor grid (offset past the cell counts)
  let dcell = corridorCell(p.x, p.y);
  atomicAdd(&atomics[P.numCells + dcell], 1u);
}

fn recordSeparation(x: f32, y: f32, memberType: i32, cause: f32) {
  let e = atomicAdd(&sep[0], 1u);
  if (i32(e) < P.sepCap) {
    let base = 1 + i32(e) * 4;
    atomicStore(&sep[base + 0], bitcast<u32>(x));
    atomicStore(&sep[base + 1], bitcast<u32>(y));
    atomicStore(&sep[base + 2], bitcast<u32>(f32(memberType)));
    atomicStore(&sep[base + 3], bitcast<u32>(cause));
  }
}

// ---------------------------------------------------------------------- step
@compute @workgroup_size(64)
fn step(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= P.nAgents) { return; }

  let s = stateIn[i];
  let p = s.xy;
  let v = s.zw;

  // Parked / inactive agents persist unchanged.
  if (!isActive(i) || isParked(p)) {
    stateOut[i] = s;
    return;
  }

  let m = meta[i];
  let typeId = m.x;
  let gIdx = m.y;
  let famStart = m.z;
  let famCount = m.w;
  let amGuardian = (gIdx == i);
  let ri = typeRadius(typeId);
  let mass = typeMass(typeId);

  // --- panic field (raises desired speed near the trigger) ---
  var panic = 0.0;
  if (P.panicActive > 0.5) {
    let dpx = p.x - P.panicX;
    let dpy = p.y - P.panicY;
    if (dpx * dpx + dpy * dpy < P.panicRadius * P.panicRadius) { panic = 1.0; }
  }

  // --- desired speed: guardians pace + wait for lagging dependents ---
  var v0 = typeV0(typeId);
  if (amGuardian && famCount > 1) {
    var slowest = v0;
    var dmax = 0.0;
    for (var j = famStart; j < famStart + famCount; j = j + 1) {
      if (j == i) { continue; }
      let vj = typeV0(meta[j].x);
      if (vj < slowest) { slowest = vj; }
      if (lost[j] == 0u) {
        let qp = stateIn[j].xy;
        let dd = length(qp - p);
        if (dd > dmax) { dmax = dd; }
      }
    }
    v0 = slowest;
    if (dmax > P.waitDist) { v0 = 0.05; }
  }
  v0 = v0 * (1.0 + P.panicBoost * panic);
  if (lost[i] == 1u) { v0 = v0 * P.lostSpeedFactor; }

  // --- driving force toward the ghat (navfield desired direction) ---
  let dcell = corridorCell(p.x, p.y);
  let nb = dcell * 5;
  let ex = nav[nb + 0];
  let ey = nav[nb + 1];
  var f = vec2<f32>(
    mass * (v0 * ex - v.x) / P.tau,
    mass * (v0 * ey - v.y) / P.tau,
  );

  // --- agent-agent forces over the 3x3 neighbour cells ---
  var near = 0;
  let cx = clamp(i32((p.x - P.xMin) / P.gridCs), 0, P.gx - 1);
  let cy = clamp(i32((p.y - P.yMin) / P.gridCs), 0, P.gy - 1);
  for (var ncy = cy - 1; ncy <= cy + 1; ncy = ncy + 1) {
    if (ncy < 0 || ncy >= P.gy) { continue; }
    for (var ncx = cx - 1; ncx <= cx + 1; ncx = ncx + 1) {
      if (ncx < 0 || ncx >= P.gx) { continue; }
      let cell = ncy * P.gx + ncx;
      let cnt = min(i32(atomicLoad(&atomics[cell])), P.maxPerCell);
      for (var s2 = 0; s2 < cnt; s2 = s2 + 1) {
        let j = i32(bucket[cell * P.maxPerCell + s2]);
        if (j == i) { continue; }
        let qp = stateIn[j].xy;
        let qv = stateIn[j].zw;
        let dx = p.x - qp.x;
        let dy = p.y - qp.y;
        let d = sqrt(dx * dx + dy * dy);
        if (d > P.rCut || d < 1e-9) { continue; }
        if (d < 1.0) { near = near + 1; }
        let nx = dx / d;
        let ny = dy / d;
        let rij = ri + typeRadius(meta[j].x);
        let overlap = rij - d;
        var frep = P.A * exp(overlap / P.B);
        if (overlap > 0.0) { frep = frep + P.k * overlap; }
        f.x = f.x + frep * nx;
        f.y = f.y + frep * ny;
        if (overlap > 0.0) {
          let tx = -ny;
          let ty = nx;
          let dvt = (qv.x - v.x) * tx + (qv.y - v.y) * ty;
          let ff = P.kappa * overlap * dvt;
          f.x = f.x + ff * tx;
          f.y = f.y + ff * ty;
        }
      }
    }
  }

  // --- wall force (nearest wall, navfield normal) ---
  let dw = nav[nb + 2];
  if (dw < P.rCut) {
    let wnx = nav[nb + 3];
    let wny = nav[nb + 4];
    let overlapW = ri - dw;
    var fwall = P.A * exp(overlapW / P.B);
    if (overlapW > 0.0) { fwall = fwall + P.k * overlapW; }
    f.x = f.x + fwall * wnx;
    f.y = f.y + fwall * wny;
    if (overlapW > 0.0) {
      let tx = -wny;
      let ty = wnx;
      let dvt = -(v.x * tx + v.y * ty);
      let ff = P.kappa * overlapW * dvt;
      f.x = f.x + ff * tx;
      f.y = f.y + ff * ty;
    }
  }

  // --- police deployment: lateral spreading force within control radius ---
  for (var k = 0; k < POL.count; k = k + 1) {
    let u = POL.units[k];
    let dpx = p.x - u.x;
    let dpy = p.y - u.y;
    let dpd = sqrt(dpx * dpx + dpy * dpy);
    if (dpd < u.z && dpd > 1e-6) {
      let rx = dpx / dpd;
      let ry = dpy / dpd;
      let dotp = rx * ex + ry * ey;
      let lx = rx - dotp * ex; // strip the along-heading component
      let ly = ry - dotp * ey;
      let ln = sqrt(lx * lx + ly * ly);
      if (ln > 1e-6) {
        let mag = u.w * exp(-dpd / (0.5 * u.z));
        f.x = f.x + mag * lx / ln;
        f.y = f.y + mag * ly / ln;
      }
    }
  }

  // --- family cohesion + emergent separation (dependents only) ---
  if (!amGuardian && gIdx >= 0 && lost[i] == 0u) {
    let gp = stateIn[gIdx].xy;
    let dx = gp.x - p.x;
    let dy = gp.y - p.y;
    let d = sqrt(dx * dx + dy * dy);
    let inStaging = p.y > P.yMax - P.spawnBandDepth;
    let crushed = near >= P.crushCount;
    if (d > P.hardBreakDist || (d > P.breakDist && crushed && !inStaging)) {
      lost[i] = 1u;
      recordSeparation(p.x, p.y, typeId, 1.0); // crush
    } else if (d > P.comfortDist) {
      let mag = min(P.kCohesion * (d - P.comfortDist), P.fCohesionMax);
      f.x = f.x + mag * dx / d;
      f.y = f.y + mag * dy / d;
    }
  }

  // --- semi-implicit Euler + speed clamp ---
  let a = f / mass;
  var vn = v + a * P.dt;
  let speed = length(vn);
  let vcap = min(P.vMaxFactor * max(v0, 0.3), 4.0);
  if (speed > vcap) { vn = vn * (vcap / max(speed, 1e-9)); }
  var pn = p + vn * P.dt;

  // hard containment: keep agents inside the walkable corridor (ports _clamp_to_walkable)
  pn.y = clamp(pn.y, 0.0, P.lengthM);
  let hw = corHalfW(pn.y) - 0.1;
  if (pn.x > hw) { pn.x = hw; vn.x = vn.x * 0.5; }
  if (pn.x < -hw) { pn.x = -hw; vn.x = vn.x * 0.5; }

  stateOut[i] = vec4<f32>(pn.x, pn.y, vn.x, vn.y);
}

// --------------------------------------------------------------------- stage
// Recirculation: only the guardian writes its family's block. When the guardian
// reaches the ghat, the whole family re-stages at the entrance (or parks if the
// family is now beyond the active population). Mirrors _remove_arrived + spawn.
@compute @workgroup_size(64)
fn stage(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= P.nAgents) { return; }
  let m = meta[i];
  if (m.y != i) { return; } // not the family's guardian
  let famStart = m.z;
  let famCount = m.w;

  let gp = stateOut[i].xy;
  let active = isActive(i);
  let reachedSink = (!isParked(gp)) && (gp.y <= P.sinkThresh);
  let parkedButActive = active && isParked(gp);

  if (active && (reachedSink || parkedButActive)) {
    // guardian_left separations: a dependent still far behind at handover.
    if (reachedSink) {
      for (var j = famStart; j < famStart + famCount; j = j + 1) {
        if (j == i || lost[j] == 1u) { continue; }
        let qp = stateOut[j].xy;
        if (length(qp - gp) > P.breakDist) {
          recordSeparation(qp.x, qp.y, meta[j].x, 2.0); // guardian_left
        }
      }
    }
    // fresh staging cluster at the entrance band
    let seed = u32(i) * 2654435761u + P.frame * 40503u;
    let cyc = P.entranceY - rand(seed) * P.spawnBandDepth;
    let cxc = (rand(seed + 7u) * 2.0 - 1.0) * P.entranceHalfW;
    for (var j = famStart; j < famStart + famCount; j = j + 1) {
      var x = cxc;
      var y = cyc;
      if (j != famStart) {
        x = clamp(cxc + (rand(u32(j) * 9176u + P.frame) * 2.0 - 1.0) * 1.2,
                  -P.entranceHalfW, P.entranceHalfW);
        y = clamp(cyc + (rand(u32(j) * 6151u + P.frame) * 2.0 - 1.0) * 1.2,
                  P.yMax - P.spawnBandDepth, P.yMax - 0.5);
      }
      stateOut[j] = vec4<f32>(x, y, 0.0, -0.2);
      lost[j] = 0u;
    }
  } else if (!active && reachedSink) {
    // population shrank: park the whole family off-screen as it exits.
    for (var j = famStart; j < famStart + famCount; j = j + 1) {
      stateOut[j] = vec4<f32>(SENTINEL + 10.0, SENTINEL + 10.0, 0.0, 0.0);
      lost[j] = 0u;
    }
  }
}
