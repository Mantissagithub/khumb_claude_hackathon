"""Navigation and wall fields over a :class:`Corridor`, via fast marching.

Two scalar fields are solved with the Eikonal fast-marching method (scikit-fmm):

    dist_to_sink   geodesic distance (m) from every walkable cell to the ghat,
                   routed *around* walls — the basis of each agent's desired
                   heading (Helbing's driving term ``(v0·e − v)/τ``).
    dist_to_wall   distance (m) from every cell to the nearest non-walkable cell,
                   giving the wall-repulsion direction for the social-force model.

Both fields are sampled (nearest-cell, vectorised) by the engine each step.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import skfmm

from .corridor import Corridor


@dataclass
class NavField:
    corridor: Corridor
    dist_to_sink: np.ndarray   # [ny, nx]  geodesic metres to ghat (inf off-domain)
    e_sink_x: np.ndarray       # [ny, nx]  unit desired-direction toward ghat
    e_sink_y: np.ndarray
    dist_to_wall: np.ndarray   # [ny, nx]  metres to nearest wall (0 outside)
    n_wall_x: np.ndarray       # [ny, nx]  unit direction away from nearest wall
    n_wall_y: np.ndarray

    # -- vectorised nearest-cell samplers --------------------------------- #
    def _idx(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = self.corridor
        ix = np.clip(((x - c.x_min) / c.cell_m).astype(np.int64), 0, c.nx - 1)
        iy = np.clip(((y - c.y_min) / c.cell_m).astype(np.int64), 0, c.ny - 1)
        return iy, ix

    def desired_dir(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        iy, ix = self._idx(x, y)
        return self.e_sink_x[iy, ix], self.e_sink_y[iy, ix]

    def wall(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        iy, ix = self._idx(x, y)
        return self.dist_to_wall[iy, ix], self.n_wall_x[iy, ix], self.n_wall_y[iy, ix]


def build_navfield(corridor: Corridor, exit_top: bool = False) -> NavField:
    """Solve the navigation field toward the ghat sink (default) or, for an
    evacuation, toward the top exit (``exit_top=True``)."""
    c = corridor
    cell = c.cell_m
    walkable = c.walkable

    # --- geodesic distance to the sink, routed around walls -------------- #
    # phi's zero contour sits at the sink; non-walkable cells are masked out so
    # the marching front must travel through the walkable corridor only.
    if exit_top:
        sink = np.zeros_like(walkable)
        sink[c.ny - 1, :] = walkable[c.ny - 1, :]  # top row = the exit
    else:
        sink = c.sink_mask
    phi = np.ones((c.ny, c.nx))
    phi[sink] = -1.0
    phi_masked = np.ma.MaskedArray(phi, mask=~walkable)
    dist_to_sink = np.ma.filled(np.abs(skfmm.distance(phi_masked, dx=cell)), np.inf)

    # Desired direction = -∇(dist_to_sink), normalised. Compute the gradient on a
    # finite copy (inf -> large) and only trust it on walkable cells.
    finite = np.where(np.isfinite(dist_to_sink), dist_to_sink, dist_to_sink[np.isfinite(dist_to_sink)].max() + 10 * cell)
    gy, gx = np.gradient(finite, cell)
    ex, ey = -gx, -gy
    norm = np.hypot(ex, ey)
    norm[norm == 0] = 1.0
    e_sink_x = np.where(walkable, ex / norm, 0.0)
    e_sink_y = np.where(walkable, ey / norm, 0.0)

    # --- distance to nearest wall + inward normal ------------------------ #
    # Signed distance to the walkable boundary: positive inside the corridor.
    phi_wall = np.where(walkable, 1.0, -1.0)
    signed = skfmm.distance(phi_wall, dx=cell)
    dist_to_wall = np.where(walkable, np.clip(signed, 0.0, None), 0.0)
    wy, wx = np.gradient(signed, cell)  # gradient points toward increasing dist = inward
    wnorm = np.hypot(wx, wy)
    wnorm[wnorm == 0] = 1.0
    n_wall_x = np.where(walkable, wx / wnorm, 0.0)
    n_wall_y = np.where(walkable, wy / wnorm, 0.0)

    return NavField(
        corridor=c,
        dist_to_sink=dist_to_sink,
        e_sink_x=e_sink_x,
        e_sink_y=e_sink_y,
        dist_to_wall=dist_to_wall,
        n_wall_x=n_wall_x,
        n_wall_y=n_wall_y,
    )
