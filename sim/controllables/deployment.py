"""Translate a DeploymentPlan into forces and metering the engine applies.

Police units add a bounded repulsive force inside their control radius, which
spreads the crowd out and lowers local density (and hence crowd pressure). A
larger ``squad`` covers more ground than a single ``constable``. Barricades and
explicit barriers meter the downward flow across a line: only ``throughput_cap``
persons per second are released past the line each step; the rest are held above
it. This is the dominant lever for relieving a downstream throat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from shared.schema import CameraState, DeploymentPlan
from sim.geometry import Corridor


@dataclass(frozen=True)
class PoliceParam:
    control_radius: float  # m
    strength: float        # N at the unit's position (decays with distance)


# Larger units cover more ground. Strengths are kept well below the family
# cohesion cap (~1500 N) so officers gently organize/space the crowd without
# overwhelming a guardian's grip and tearing dependents away.
POLICE_PARAMS: dict[str, PoliceParam] = {
    "constable": PoliceParam(control_radius=2.5, strength=150.0),
    "squad":     PoliceParam(control_radius=5.0, strength=350.0),
    # A 'barricade' force allocation becomes a metering gate (see Deployment).
    "barricade": PoliceParam(control_radius=0.0, strength=0.0),
}

_BARRICADE_DEFAULT_CAP = 2.5  # persons/s released past a bare 'barricade' unit


@dataclass
class _MeterGate:
    y_line: float        # metric y of the gate
    x_lo: float
    x_hi: float
    cap: float           # persons/s allowed to cross downward
    accumulator: float = 0.0


class Deployment:
    def __init__(self, corridor: Corridor, plan: DeploymentPlan):
        self.corridor = corridor
        self.plan = plan
        proj = corridor.proj

        # Police point-repellers (constable/squad).
        self._px: list[float] = []
        self._py: list[float] = []
        self._radius: list[float] = []
        self._strength: list[float] = []
        self.gates: list[_MeterGate] = []

        for f in plan.force_allocations:
            x, y = proj.to_xy(f.lng, f.lat)
            if f.unit_type == "barricade":
                self.gates.append(self._gate_across(y, _BARRICADE_DEFAULT_CAP))
            else:
                p = POLICE_PARAMS.get(f.unit_type, POLICE_PARAMS["constable"])
                self._px.append(x)
                self._py.append(y)
                self._radius.append(p.control_radius)
                self._strength.append(p.strength)

        # Explicit barrier lines -> metering gates at their mean y.
        for b in plan.barriers:
            x1, y1 = proj.to_xy(b.lng1, b.lat1)
            x2, y2 = proj.to_xy(b.lng2, b.lat2)
            y_line = 0.5 * (y1 + y2)
            self.gates.append(
                _MeterGate(y_line=y_line, x_lo=min(x1, x2), x_hi=max(x1, x2), cap=max(b.throughput_cap, 0.1))
            )

        self._pxa = np.array(self._px)
        self._pya = np.array(self._py)
        self._ra = np.array(self._radius)
        self._sa = np.array(self._strength)

    def _gate_across(self, y_line: float, cap: float) -> _MeterGate:
        # A barricade unit meters the full corridor width at its y.
        half = self.corridor.width_at(y_line) / 2.0
        return _MeterGate(y_line=y_line, x_lo=-half, x_hi=half, cap=cap)

    # -- Controllables protocol ------------------------------------------ #
    def force_contrib(self, sim) -> tuple[np.ndarray, np.ndarray]:
        n = sim.n
        fx = np.zeros(n)
        fy = np.zeros(n)
        if self._pxa.size == 0 or n == 0:
            return fx, fy
        # Officers prevent lateral bunching / cross-flow but must NOT block the
        # procession: project the repulsion onto the direction perpendicular to
        # each agent's desired heading, so it spreads the crowd sideways (lowering
        # density and pressure) and never pushes anyone backward.
        ex, ey = sim.nav.desired_dir(sim.px, sim.py)
        for k in range(self._pxa.size):
            dx = sim.px - self._pxa[k]
            dy = sim.py - self._pya[k]
            d = np.hypot(dx, dy)
            within = (d < self._ra[k]) & (d > 1e-6)
            if not within.any():
                continue
            rx = dx[within] / d[within]
            ry = dy[within] / d[within]
            # Remove the component along the desired heading -> lateral only.
            dot = rx * ex[within] + ry * ey[within]
            lx = rx - dot * ex[within]
            ly = ry - dot * ey[within]
            lnorm = np.hypot(lx, ly)
            ok = lnorm > 1e-6
            mag = self._sa[k] * np.exp(-d[within] / (0.5 * self._ra[k]))
            fxw = np.zeros(within.sum())
            fyw = np.zeros(within.sum())
            fxw[ok] = mag[ok] * lx[ok] / lnorm[ok]
            fyw[ok] = mag[ok] * ly[ok] / lnorm[ok]
            fx[within] += fxw
            fy[within] += fyw
        return fx, fy

    def meter(self, sim) -> None:
        """Hold-and-release: cap downward crossings past each gate per step."""
        dt = sim.cfg.dt
        for g in self.gates:
            g.accumulator += g.cap * dt
            # Agents queued in a thin band just above the line (any velocity).
            band = (
                (sim.py > g.y_line)
                & (sim.py <= g.y_line + 1.0)
                & (sim.px >= g.x_lo)
                & (sim.px <= g.x_hi)
            )
            idx = np.where(band)[0]
            if idx.size == 0:
                continue
            allowed = int(g.accumulator)
            # Release the `allowed` agents nearest the line; block the rest from
            # crossing downward. They stack upstream at SFM-bounded density rather
            # than being pinned to the line (which would create a false crush).
            order = idx[np.argsort(sim.py[idx])]
            hold = order[allowed:]
            g.accumulator -= min(allowed, idx.size)
            if hold.size:
                sim.vy[hold] = np.maximum(sim.vy[hold], 0.0)  # no downward motion
                below = hold[sim.py[hold] < g.y_line]
                sim.py[below] = g.y_line

    # -- CCTV (sensing, not physics) ------------------------------------- #
    def apply_cctv(self, cameras: list[CameraState]) -> list[CameraState]:
        """Return a copy of the inventory with re-aims from the plan applied."""
        by_id = {c.camera_id: c for c in cameras}
        out = [CameraState(c.camera_id, c.lng, c.lat, c.heading_deg, c.fov_deg, c.range_m) for c in cameras]
        out_by_id = {c.camera_id: c for c in out}
        for r in self.plan.cctv_reaims:
            if r.camera_id in out_by_id:
                out_by_id[r.camera_id].heading_deg = r.heading_deg
        return out
