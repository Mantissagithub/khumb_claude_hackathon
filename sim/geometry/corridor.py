"""Parametric corridor domain anchored to real geography.

The provided data has only point coordinates (ghat centroids, chokepoints, CCTV,
police) — not walkable polygons. So the corridor's *meter-scale shape* is an
explicit model: a length, a width profile that narrows to a throat near the ghat,
and a cell-grid walkable mask. The anchor and approach bearing are real (from
``data/data``); the throat geometry is the modelled part, refinable later from OSM
footpaths or satellite imagery (that is exactly what ``sim/observation`` is for).

Default corridor = the **Ramkund ghat approach**, Nashik/Panchavati: the site of
the 2003 stampede (39 dead in a narrow ghat approach) and the top separation
location in the synthetic dataset. Geometry is config-driven so Trimbak/Kushavarta
can be swapped in by changing ``CorridorConfig`` alone.

Local metric frame (see ``shared.geo``):
    * origin = ghat water edge (the sink)
    * +y     = away from the ghat, up the approach toward the plaza/entrance
    * +x     = across the corridor (lateral)
Grid arrays are indexed ``[iy, ix]``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from shared.geo import LocalProjection


@dataclass(frozen=True)
class CorridorConfig:
    corridor_id: str
    anchor_lng: float          # real ghat coordinate (sink), from data/data
    anchor_lat: float
    length_m: float            # extent of the approach modelled (ghat -> entrance)
    wide_width_m: float        # corridor width at the plaza/entrance end
    narrow_width_m: float      # width at the throat near the ghat (the danger)
    throat_len_m: float        # length of the narrow throat measured from the ghat
    cell_m: float = 0.5        # grid resolution (m); 0.5 m << ~0.25 m agent radius
    bearing_deg: float = 0.0   # compass bearing of the approach axis (for export)


# The real Ramkund / Godavari ghat access point (data/data/Chokepoints_Parking.csv:
# "Ramkund", "Panchavati / Ramkund access zone", "Godavari Ghat approaches").
RAMKUND = CorridorConfig(
    corridor_id="ramkund",
    anchor_lng=73.79062,
    anchor_lat=20.00670,
    length_m=60.0,
    wide_width_m=28.0,
    narrow_width_m=6.0,
    throat_len_m=14.0,
    cell_m=0.5,
    bearing_deg=20.0,
)


class Corridor:
    """A discretised walkable domain with a width profile that narrows to a throat."""

    def __init__(self, cfg: CorridorConfig):
        self.cfg = cfg
        self.proj = LocalProjection(anchor_lng=cfg.anchor_lng, anchor_lat=cfg.anchor_lat)

        c = cfg.cell_m
        self.cell_m = c
        self.x_min = -cfg.wide_width_m / 2.0
        self.x_max = +cfg.wide_width_m / 2.0
        self.y_min = 0.0
        self.y_max = cfg.length_m

        self.nx = int(np.ceil((self.x_max - self.x_min) / c))
        self.ny = int(np.ceil((self.y_max - self.y_min) / c))

        # Cell-center coordinate vectors (metres).
        self.xs = self.x_min + (np.arange(self.nx) + 0.5) * c
        self.ys = self.y_min + (np.arange(self.ny) + 0.5) * c

        self.walkable = self._build_walkable()      # [ny, nx] bool
        self.sink_mask = self._build_sink_mask()    # [ny, nx] bool (ghat water edge)
        self.entrance_y = self.y_max - c             # spawn band, top of corridor

    # -- geometry ---------------------------------------------------------- #
    def width_at(self, y: float | np.ndarray) -> float | np.ndarray:
        """Corridor width (m) at distance ``y`` from the ghat.

        Stays at ``narrow_width_m`` through the throat (0 .. throat_len_m), then
        opens linearly to ``wide_width_m`` at the plaza end.
        """
        cfg = self.cfg
        y = np.asarray(y, dtype=float)
        span = max(cfg.length_m - cfg.throat_len_m, 1e-6)
        frac = np.clip((y - cfg.throat_len_m) / span, 0.0, 1.0)
        w = cfg.narrow_width_m + (cfg.wide_width_m - cfg.narrow_width_m) * frac
        return w if w.ndim else float(w)

    def _build_walkable(self) -> np.ndarray:
        # |x| <= half-width(y) for each cell.
        half_w = np.asarray(self.width_at(self.ys)) / 2.0          # [ny]
        xx = np.abs(self.xs)[None, :]                               # [1, nx]
        return xx <= half_w[:, None]                               # [ny, nx]

    def _build_sink_mask(self) -> np.ndarray:
        # The ghat water edge: bottom row of walkable cells (y ~ 0).
        m = np.zeros((self.ny, self.nx), dtype=bool)
        m[0, :] = self.walkable[0, :]
        return m

    # -- index <-> metric helpers ----------------------------------------- #
    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        ix = int((x - self.x_min) / self.cell_m)
        iy = int((y - self.y_min) / self.cell_m)
        return iy, ix

    def in_bounds(self, iy: int, ix: int) -> bool:
        return 0 <= iy < self.ny and 0 <= ix < self.nx

    def is_walkable_xy(self, x: float, y: float) -> bool:
        iy, ix = self.cell_of(x, y)
        return self.in_bounds(iy, ix) and bool(self.walkable[iy, ix])

    def at_sink_xy(self, x: float, y: float) -> bool:
        """An agent has reached the ghat (and will be removed) at y <= one cell."""
        return y <= self.y_min + self.cell_m and self.is_walkable_xy(x, y)
