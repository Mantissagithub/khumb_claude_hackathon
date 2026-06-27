"""The microscopic crowd simulation: state, stepping, spawning, family bonds.

Holds per-agent state as parallel numpy arrays, advances them with the Social
Force Model kernel (``forces.py``), keeps families together with a cohesion force,
and — the part Setu cares about — logs a **separation event** whenever crowd
pressure tears a dependent away from its guardian.

Controllables (police, barriers, CCTV) are injected via an optional object with a
``force_contrib`` hook and a ``meter`` hook, so the engine stays decoupled from
the deployment layer (built in ``sim/controllables``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

import numpy as np

from sim.agents.types import FALL_RISK, MASS, RADIUS, V0, generate_party
from sim.geometry import Corridor, NavField

from .forces import build_cell_list, compute_forces
from .params import SFMParams


class Controllables(Protocol):
    """What the engine needs from a deployment (implemented in sim/controllables)."""

    def force_contrib(self, sim: "Simulation") -> tuple[np.ndarray, np.ndarray]:
        """Extra (fx, fy) per active agent from police repellers / barriers."""

    def meter(self, sim: "Simulation") -> None:
        """Mutate agent state in place to enforce throughput caps at barrier gates."""


@dataclass
class SeparationEvent:
    t: float
    x: float
    y: float
    lng: float
    lat: float
    member_type: int
    guardian_type: int
    cause: str  # "crush" (pulled apart) | "guardian_left" (guardian reached ghat first)


@dataclass
class SimConfig:
    dt: float = 0.02
    seed: int = 0
    # Family cohesion (Moussaïd et al. 2010, simplified):
    comfort_dist: float = 1.0    # below this, no cohesion pull
    wait_dist: float = 2.5       # guardian waits if a dependent lags past this
    break_dist: float = 4.0      # guardian-left split distance at the ghat
    k_cohesion: float = 350.0    # cohesion spring stiffness (N/m)
    f_cohesion_max: float = 1500.0
    lost_speed_factor: float = 0.45  # a separated dependent slows and mills
    # Separation is a crowd-turbulence phenomenon: above a critical crowd pressure
    # the local flow becomes turbulent and shoves people in random directions,
    # tearing dependents from guardians (Helbing 2007). Calibrated so baseline flow
    # stays below p_crit and the surge/stampede throat exceeds it.
    p_crit: float = 0.30        # crowd-pressure separation threshold (1/s^2)
    p_scale: float = 0.60       # pressure excess that saturates the break hazard
    sep_rate: float = 0.8       # max bond-break hazard (per second) at saturation
    hard_break_dist: float = 12.0  # past this they are lost regardless (carried away)
    spawn_band_depth: float = 5.0  # depth (m) of the entrance staging band
    spawn_min_gap: float = 0.7     # min spacing (m) between spawned agents
    sink_at_top: bool = False      # evacuation: agents leave via the top exit


class Simulation:
    def __init__(
        self,
        corridor: Corridor,
        navfield: NavField,
        arrival_rate: Callable[[float], float],
        sfm: Optional[SFMParams] = None,
        cfg: Optional[SimConfig] = None,
        controllables: Optional[Controllables] = None,
    ):
        self.corridor = corridor
        self.nav = navfield
        self.arrival_rate = arrival_rate
        self.sfm = sfm or SFMParams()
        self.cfg = cfg or SimConfig()
        self.controllables = controllables
        self.rng = np.random.default_rng(self.cfg.seed)

        self.t = 0.0
        self._next_group_id = 0
        self._next_agent_id = 0

        # Parallel state arrays (all length == number of active agents).
        self.px = np.zeros(0)
        self.py = np.zeros(0)
        self.vx = np.zeros(0)
        self.vy = np.zeros(0)
        self.type_id = np.zeros(0, dtype=np.int64)
        self.group_id = np.zeros(0, dtype=np.int64)
        self.is_guardian = np.zeros(0, dtype=bool)
        self.agent_id = np.zeros(0, dtype=np.int64)
        self.panic = np.zeros(0)        # 0..1, raises desired speed
        self.lost = np.zeros(0, dtype=bool)  # separated dependent
        self.local_count = np.zeros(0, dtype=np.int64)  # neighbours within 1 m
        self.local_density = np.zeros(0)   # persons / m^2 in the 1 m disc
        self.local_velvar = np.zeros(0)    # local velocity variance (m^2/s^2)
        self.local_pressure = np.zeros(0)  # crowd pressure = density * velvar (1/s^2)

        # Spatial-hash grid sized to the interaction cutoff.
        cs = self.sfm.r_cut
        self._cs = cs
        self._gx = int(np.ceil((corridor.x_max - corridor.x_min) / cs))
        self._gy = int(np.ceil((corridor.y_max - corridor.y_min) / cs))

        self.separations: list[SeparationEvent] = []
        self.arrived_count = 0
        self._spawn_accumulator = 0.0

    # ------------------------------------------------------------------ #
    @property
    def n(self) -> int:
        return self.px.shape[0]

    def _desired_speed(self) -> np.ndarray:
        v0 = V0[self.type_id].copy()
        # A guardian walks at its slowest dependent's pace (holds the child's
        # hand), so families don't string out and "separate" just by queueing.
        bonded_g = np.where((self.group_id >= 0) & self.is_guardian)[0]
        if bonded_g.size:
            slowest: dict[int, float] = {}
            for i in np.where(self.group_id >= 0)[0]:
                gid = int(self.group_id[i])
                v = V0[self.type_id[i]]
                if gid not in slowest or v < slowest[gid]:
                    slowest[gid] = float(v)
            for gi in bonded_g:
                gid = int(self.group_id[gi])
                v0[gi] = slowest[gid]  # walk at the slowest dependent's pace
                # If a dependent lags beyond wait_dist, stop and wait for them.
                deps = np.where((self.group_id == gid) & ~self.is_guardian & ~self.lost)[0]
                if deps.size:
                    dmax = float(np.max(np.hypot(self.px[deps] - self.px[gi], self.py[deps] - self.py[gi])))
                    if dmax > self.cfg.wait_dist:
                        v0[gi] = 0.05
        v0 *= 1.0 + self.sfm.panic_speed_boost * self.panic
        v0[self.lost] *= self.cfg.lost_speed_factor
        return v0

    # ------------------------------------------------------------------ #
    def step(self) -> None:
        cfg, sfm, cor, nav = self.cfg, self.sfm, self.corridor, self.nav
        dt = cfg.dt

        if self.n > 0:
            radius = RADIUS[self.type_id]
            mass = MASS[self.type_id]
            v0_eff = self._desired_speed()
            ex, ey = nav.desired_dir(self.px, self.py)
            wd, wnx, wny = nav.wall(self.px, self.py)

            order, start, cx, cy = build_cell_list(
                self.px, self.py, cor.x_min, cor.y_min, self._cs, self._gx, self._gy
            )
            fx, fy, self.local_count, self.local_velvar = compute_forces(
                self.px, self.py, self.vx, self.vy, radius, mass, v0_eff, ex, ey,
                wd, wnx, wny, order, start, cx, cy, self._gx, self._gy,
                sfm.A, sfm.B, sfm.k, sfm.kappa, sfm.tau,
            )
            # Crowd pressure (Helbing 2007): local density x velocity variance.
            # Density from the 1 m-radius disc (area pi); self + neighbours.
            self.local_density = (self.local_count + 1.0) / np.pi
            self.local_pressure = self.local_density * self.local_velvar

            # Family cohesion + emergent separation detection.
            fcx, fcy = self._cohesion_forces()
            fx += fcx
            fy += fcy

            # Controllable deployments (police repellers, barrier walls).
            if self.controllables is not None:
                gx_extra, gy_extra = self.controllables.force_contrib(self)
                fx += gx_extra
                fy += gy_extra

            # Semi-implicit Euler with a speed clamp for numerical stability.
            ax = fx / mass
            ay = fy / mass
            self.vx += ax * dt
            self.vy += ay * dt
            speed = np.hypot(self.vx, self.vy)
            vcap = np.minimum(sfm.v_max_factor * np.maximum(v0_eff, 0.3), 4.0)
            over = speed > vcap
            scale = np.where(over, vcap / np.maximum(speed, 1e-9), 1.0)
            self.vx *= scale
            self.vy *= scale
            self.px += self.vx * dt
            self.py += self.vy * dt

            self._clamp_to_walkable()

            if self.controllables is not None:
                self.controllables.meter(self)

        self._remove_arrived()
        self._spawn(dt)
        self.t += dt

    # ------------------------------------------------------------------ #
    def _cohesion_forces(self) -> tuple[np.ndarray, np.ndarray]:
        """Pull dependents toward their guardian; snap the bond under crush."""
        fx = np.zeros(self.n)
        fy = np.zeros(self.n)
        cfg = self.cfg

        bonded = self.group_id >= 0
        if not bonded.any():
            return fx, fy

        # Map group_id -> guardian index (only among currently active agents).
        guardian_of: dict[int, int] = {}
        for i in np.where(bonded & self.is_guardian)[0]:
            guardian_of[int(self.group_id[i])] = int(i)

        for i in np.where(bonded & ~self.is_guardian & ~self.lost)[0]:
            gid = int(self.group_id[i])
            gi = guardian_of.get(gid)
            if gi is None:
                continue  # guardian already removed; handled at removal time
            dx = self.px[gi] - self.px[i]
            dy = self.py[gi] - self.py[i]
            d = float(np.hypot(dx, dy))
            # The entrance staging band is low-pressure (people still spreading out);
            # don't let a tight spawn cluster be mistaken for a crush.
            in_staging = self.py[i] > self.corridor.y_max - cfg.spawn_band_depth
            if d > cfg.hard_break_dist:
                self._record_separation(i, gi, cause="carried_away")
                continue
            # Crowd-turbulence tearing: hazard rises with pressure above p_crit.
            if not in_staging and self.local_pressure.size:
                excess = self.local_pressure[i] - cfg.p_crit
                if excess > 0.0:
                    hazard = min(excess / cfg.p_scale, 1.0) * cfg.sep_rate
                    if self.rng.random() < hazard * cfg.dt:
                        self._record_separation(i, gi, cause="crush")
                        continue
            if d > cfg.comfort_dist:
                mag = min(cfg.k_cohesion * (d - cfg.comfort_dist), cfg.f_cohesion_max)
                fx[i] += mag * dx / d
                fy[i] += mag * dy / d

        # (Guardians waiting for a lagging dependent is handled in _desired_speed,
        # which zeroes their desired speed — a far stronger brake than a damping
        # term, so families actually hold together until a real crush separates them.)
        return fx, fy

    def _record_separation(self, i: int, gi: int, cause: str) -> None:
        lng, lat = self.corridor.proj.to_lnglat(float(self.px[i]), float(self.py[i]))
        self.separations.append(
            SeparationEvent(
                t=self.t,
                x=float(self.px[i]),
                y=float(self.py[i]),
                lng=lng,
                lat=lat,
                member_type=int(self.type_id[i]),
                guardian_type=int(self.type_id[gi]),
                cause=cause,
            )
        )
        self.group_id[i] = -1
        self.lost[i] = True

    # ------------------------------------------------------------------ #
    def _clamp_to_walkable(self) -> None:
        """Safety net: nudge any agent pushed through a wall back inside."""
        wd, wnx, wny = self.nav.wall(self.px, self.py)
        # Outside the walkable mask -> wall_dist sampled as 0; push along inward normal.
        cor = self.corridor
        iy = np.clip(((self.py - cor.y_min) / cor.cell_m).astype(np.int64), 0, cor.ny - 1)
        ix = np.clip(((self.px - cor.x_min) / cor.cell_m).astype(np.int64), 0, cor.nx - 1)
        outside = ~cor.walkable[iy, ix]
        if outside.any():
            self.px[outside] += 0.5 * cor.cell_m * wnx[outside]
            self.py[outside] += 0.5 * cor.cell_m * wny[outside]
            self.vx[outside] *= 0.5
            self.vy[outside] *= 0.5

    def _remove_arrived(self) -> None:
        if self.n == 0:
            return
        if self.cfg.sink_at_top:
            arrived = self.py >= self.corridor.y_max - self.corridor.cell_m
        else:
            arrived = self.py <= self.corridor.y_min + self.corridor.cell_m
        if not arrived.any():
            return
        # A guardian reaching the ghat while a dependent is still far behind and
        # not yet within reach is itself a separation (family split at the water).
        for gi in np.where(arrived & self.is_guardian & (self.group_id >= 0))[0]:
            gid = int(self.group_id[gi])
            members = np.where(
                (self.group_id == gid) & ~self.is_guardian & ~self.lost & ~arrived
            )[0]
            for i in members:
                d = float(np.hypot(self.px[i] - self.px[gi], self.py[i] - self.py[gi]))
                if d > self.cfg.break_dist:
                    self._record_separation(int(i), int(gi), cause="guardian_left")

        self.arrived_count += int(arrived.sum())
        self._compact(~arrived)

    def _compact(self, keep: np.ndarray) -> None:
        self.px = self.px[keep]
        self.py = self.py[keep]
        self.vx = self.vx[keep]
        self.vy = self.vy[keep]
        self.type_id = self.type_id[keep]
        self.group_id = self.group_id[keep]
        self.is_guardian = self.is_guardian[keep]
        self.agent_id = self.agent_id[keep]
        self.panic = self.panic[keep]
        self.lost = self.lost[keep]
        self.local_count = self.local_count[keep]
        self.local_density = self.local_density[keep]
        self.local_velvar = self.local_velvar[keep]
        self.local_pressure = self.local_pressure[keep]

    # ------------------------------------------------------------------ #
    def _spawn(self, dt: float) -> None:
        """Poisson arrivals of whole parties at the entrance band."""
        self._spawn_accumulator += self.arrival_rate(self.t) * dt
        n_persons = int(self._spawn_accumulator)
        if n_persons <= 0:
            return
        spawned = 0
        attempts = 0
        while spawned < n_persons and attempts < n_persons + 20:
            attempts += 1
            party = generate_party(self.rng, self._next_group_id)
            placed = self._place_party(party)
            if placed:
                spawned += len(party)
                if len(party) > 1:
                    self._next_group_id += 1
            else:
                break  # entrance congested; try again next step
        self._spawn_accumulator -= spawned

    def _place_party(self, party: list[dict]) -> bool:
        cor = self.corridor
        y0 = cor.entrance_y
        depth = self.cfg.spawn_band_depth
        half_w = cor.width_at(y0) / 2.0 - 0.4
        # Find non-overlapping spots across the staging band for the whole party.
        # Party members are seeded close together (a family arrives as a cluster).
        spots: list[tuple[float, float]] = []
        cx0 = self.rng.uniform(-half_w, half_w)
        cy0 = y0 - self.rng.uniform(0.0, depth)
        for _ in party:
            ok = False
            for _try in range(15):
                if not spots:
                    x, y = cx0, cy0
                else:  # cluster near the party's first member
                    x = np.clip(cx0 + self.rng.uniform(-1.2, 1.2), -half_w, half_w)
                    y = np.clip(cy0 + self.rng.uniform(-1.2, 1.2), cor.y_max - depth, y0)
                if self._free_spot(x, y, spots):
                    spots.append((float(x), float(y)))
                    ok = True
                    break
            if not ok:
                return False
        for spec, (x, y) in zip(party, spots):
            self._append_agent(x, y, spec)
        return True

    def _free_spot(self, x: float, y: float, pending: list[tuple[float, float]]) -> bool:
        gap2 = self.cfg.spawn_min_gap ** 2
        if self.n > 0:
            d2 = (self.px - x) ** 2 + (self.py - y) ** 2
            if np.any(d2 < gap2):
                return False
        for (xx, yy) in pending:
            if (xx - x) ** 2 + (yy - y) ** 2 < gap2:
                return False
        return True

    def _append_agent(self, x: float, y: float, spec: dict) -> None:
        self.px = np.append(self.px, x)
        self.py = np.append(self.py, y)
        self.vx = np.append(self.vx, 0.0)
        self.vy = np.append(self.vy, -0.2)
        self.type_id = np.append(self.type_id, spec["type_id"])
        self.group_id = np.append(self.group_id, spec["group_id"])
        self.is_guardian = np.append(self.is_guardian, spec["is_guardian"])
        self.agent_id = np.append(self.agent_id, self._next_agent_id)
        self.panic = np.append(self.panic, 0.0)
        self.lost = np.append(self.lost, False)
        # Newly spawned agents have no computed crowd metrics yet (filled next step).
        self.local_count = np.append(self.local_count, 0)
        self.local_density = np.append(self.local_density, 0.0)
        self.local_velvar = np.append(self.local_velvar, 0.0)
        self.local_pressure = np.append(self.local_pressure, 0.0)
        self._next_agent_id += 1

    # ------------------------------------------------------------------ #
    def run(self, duration_s: float, recorder: Optional[Callable[["Simulation"], None]] = None,
            record_every: int = 5) -> None:
        n_steps = int(round(duration_s / self.cfg.dt))
        for s in range(n_steps):
            self.step()
            if recorder is not None and s % record_every == 0:
                recorder(self)
