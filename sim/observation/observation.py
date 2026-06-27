"""External density observation + Newtonian-nudging assimilation.

An :class:`Observation` is a per-cell crowd-density field over a corridor (the
shape a satellite/drone/CCTV-occupancy estimate would take). :func:`assimilate`
compares it to the simulation's current density and nudges agent velocities up the
density residual — toward cells the observation says are *more* crowded than the
sim currently has — relaxing the sim's distribution toward the observation without
breaking the physics. This is the standard nudging (Newtonian relaxation) form of
data assimilation, kept deliberately gentle.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sim.geometry import Corridor


@dataclass
class Observation:
    corridor_id: str
    t: float
    source: str                # e.g. "satellite", "drone", "cctv_occupancy"
    cell_m: float
    density: np.ndarray        # [ny, nx] persons / m^2 on the corridor grid

    @classmethod
    def from_points(cls, corridor: Corridor, points: list[tuple[float, float, float]],
                    cell_m: float = 1.0, t: float = 0.0, source: str = "satellite") -> "Observation":
        """Rasterise sparse ``(lng, lat, persons)`` estimates onto the corridor grid."""
        nx = int(np.ceil((corridor.x_max - corridor.x_min) / cell_m))
        ny = int(np.ceil((corridor.y_max - corridor.y_min) / cell_m))
        grid = np.zeros((ny, nx))
        for lng, lat, persons in points:
            x, y = corridor.proj.to_xy(lng, lat)
            ix = int((x - corridor.x_min) / cell_m)
            iy = int((y - corridor.y_min) / cell_m)
            if 0 <= iy < ny and 0 <= ix < nx:
                grid[iy, ix] += persons
        grid /= cell_m * cell_m
        return cls(corridor.cfg.corridor_id, t, source, cell_m, grid)


def simulated_density(sim, cell_m: float) -> np.ndarray:
    """Current per-cell density of the live simulation, on the same grid shape."""
    cor = sim.corridor
    nx = int(np.ceil((cor.x_max - cor.x_min) / cell_m))
    ny = int(np.ceil((cor.y_max - cor.y_min) / cell_m))
    grid = np.zeros((ny, nx))
    if sim.n:
        ix = np.clip(((sim.px - cor.x_min) / cell_m).astype(np.int64), 0, nx - 1)
        iy = np.clip(((sim.py - cor.y_min) / cell_m).astype(np.int64), 0, ny - 1)
        np.add.at(grid, (iy, ix), 1.0)
        grid /= cell_m * cell_m
    return grid


def assimilate(sim, obs: Observation, gain: float = 0.6, max_nudge: float = 0.6) -> float:
    """Nudge agent velocities toward the observed density. Returns the RMS residual.

    For each agent, add ``gain * ∇residual`` (residual = observed − simulated
    density) to its velocity, capped at ``max_nudge`` m/s, so agents drift toward
    under-represented cells. Gentle by design — it steers the sim, it does not
    teleport agents, so the run stays stable.
    """
    if obs.density.shape != simulated_density(sim, obs.cell_m).shape:
        raise ValueError("observation grid shape does not match the corridor grid")
    sim_d = simulated_density(sim, obs.cell_m)
    residual = obs.density - sim_d
    rms = float(np.sqrt(np.mean(residual ** 2)))
    if sim.n == 0:
        return rms

    # Gradient of the residual (toward cells the observation says are busier).
    gy, gx = np.gradient(residual, obs.cell_m)
    cor = sim.corridor
    ix = np.clip(((sim.px - cor.x_min) / obs.cell_m).astype(np.int64), 0, residual.shape[1] - 1)
    iy = np.clip(((sim.py - cor.y_min) / obs.cell_m).astype(np.int64), 0, residual.shape[0] - 1)
    nudge_x = np.clip(gain * gx[iy, ix], -max_nudge, max_nudge)
    nudge_y = np.clip(gain * gy[iy, ix], -max_nudge, max_nudge)
    sim.vx += nudge_x
    sim.vy += nudge_y
    return rms
