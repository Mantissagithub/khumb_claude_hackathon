"""Accumulate the simulation's density / pressure / separation layers over time.

Attach a :class:`MetricsRecorder` as the ``recorder`` of :meth:`Simulation.run`.
Each sampled frame it bins active agents onto a coarse metric grid (1 m cells by
default) and tracks the running peak. Afterwards it produces the situation-report
fields the planning pillar consumes (top pressure points, separation hotspots,
subzone density), plus an egress-time metric.

These are the Pillar-A outputs in AGENTS.md §3: "density heatmaps over time,
chokepoint pressure curves, predicted separation hotspots, and stampede-risk zones".
"""

from __future__ import annotations

import numpy as np

from shared.schema import PressurePoint, SeparationHotspot, SubzoneDensity
from sim.engine import Simulation


class MetricsRecorder:
    def __init__(self, sim: Simulation, cell_m: float = 1.0):
        self.sim = sim
        cor = sim.corridor
        self.cor = cor
        self.cell_m = cell_m
        self.nx = int(np.ceil((cor.x_max - cor.x_min) / cell_m))
        self.ny = int(np.ceil((cor.y_max - cor.y_min) / cell_m))
        self.cell_area = cell_m * cell_m

        # Running peaks (the risk layers) and a time-integral for the mean layer.
        self.peak_density = np.zeros((self.ny, self.nx))
        self.peak_pressure = np.zeros((self.ny, self.nx))
        self.peak_pressure_t = np.zeros((self.ny, self.nx))
        self.sum_density = np.zeros((self.ny, self.nx))
        self.frames = 0

        # Global peak and active-count timeseries (for egress).
        self.global_peak_pressure = 0.0
        self.active_ts: list[tuple[float, int]] = []

    # ------------------------------------------------------------------ #
    def _cell(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        ix = np.clip(((x - self.cor.x_min) / self.cell_m).astype(np.int64), 0, self.nx - 1)
        iy = np.clip(((y - self.cor.y_min) / self.cell_m).astype(np.int64), 0, self.ny - 1)
        return iy, ix

    def record(self, sim: Simulation) -> None:
        self.frames += 1
        self.active_ts.append((sim.t, sim.n))
        if sim.n == 0:
            return
        iy, ix = self._cell(sim.px, sim.py)

        # Per-cell agent count -> density (persons/m^2).
        counts = np.zeros((self.ny, self.nx))
        np.add.at(counts, (iy, ix), 1.0)
        density = counts / self.cell_area
        self.sum_density += density
        self.peak_density = np.maximum(self.peak_density, density)

        # Per-cell crowd pressure = max of the per-agent pressures falling in it.
        press = np.zeros((self.ny, self.nx))
        np.maximum.at(press, (iy, ix), sim.local_pressure)
        newer = press > self.peak_pressure
        self.peak_pressure = np.where(newer, press, self.peak_pressure)
        self.peak_pressure_t = np.where(newer, sim.t, self.peak_pressure_t)
        self.global_peak_pressure = max(self.global_peak_pressure, float(sim.local_pressure.max()))

    # ------------------------------------------------------------------ #
    @property
    def mean_density(self) -> np.ndarray:
        return self.sum_density / max(self.frames, 1)

    def _cell_to_lnglat(self, iy: int, ix: int) -> tuple[float, float]:
        x = self.cor.x_min + (ix + 0.5) * self.cell_m
        y = self.cor.y_min + (iy + 0.5) * self.cell_m
        return self.cor.proj.to_lnglat(x, y)

    def top_pressure_points(self, k: int = 8) -> list[PressurePoint]:
        flat = self.peak_pressure.ravel()
        if not np.any(flat > 0):
            return []
        idx = np.argsort(flat)[::-1][:k]
        out: list[PressurePoint] = []
        for fi in idx:
            if flat[fi] <= 0:
                break
            iy, ix = divmod(int(fi), self.nx)
            lng, lat = self._cell_to_lnglat(iy, ix)
            out.append(PressurePoint(lng=lng, lat=lat, value=float(flat[fi]), t=float(self.peak_pressure_t[iy, ix])))
        return out

    def separation_hotspots(self, k: int = 6) -> list[SeparationHotspot]:
        """Bin separation events to the metric grid and return the busiest cells."""
        if not self.sim.separations:
            return []
        grid = np.zeros((self.ny, self.nx))
        for e in self.sim.separations:
            iy, ix = self._cell(np.array([e.x]), np.array([e.y]))
            grid[iy[0], ix[0]] += 1
        flat = grid.ravel()
        idx = np.argsort(flat)[::-1][:k]
        out: list[SeparationHotspot] = []
        for fi in idx:
            if flat[fi] <= 0:
                break
            iy, ix = divmod(int(fi), self.nx)
            lng, lat = self._cell_to_lnglat(iy, ix)
            out.append(SeparationHotspot(lng=lng, lat=lat, count=int(flat[fi])))
        return out

    def subzone_density(self) -> list[SubzoneDensity]:
        """Mean/peak density in named bands along the approach (ghat -> plaza)."""
        cfg = self.cor.cfg
        bands = [
            ("ghat_throat", 0.0, cfg.throat_len_m),
            ("mid_approach", cfg.throat_len_m, (cfg.throat_len_m + cfg.length_m) / 2),
            ("plaza", (cfg.throat_len_m + cfg.length_m) / 2, cfg.length_m),
        ]
        ys = self.cor.y_min + (np.arange(self.ny) + 0.5) * self.cell_m
        mean_d = self.mean_density
        out: list[SubzoneDensity] = []
        for name, y0, y1 in bands:
            rows = (ys >= y0) & (ys < y1)
            if not rows.any():
                continue
            out.append(
                SubzoneDensity(
                    name=name,
                    mean_density=float(mean_d[rows].mean()),
                    peak_density=float(self.peak_density[rows].max()),
                )
            )
        return out

    def egress_time_s(self, clear_frac: float = 0.1) -> float:
        """Time at which active count first falls to <= clear_frac of its peak.

        A proxy for how long the corridor stays dangerously full. If it never
        clears within the window, returns the window end (worst case).
        """
        if not self.active_ts:
            return 0.0
        peak = max(n for _, n in self.active_ts)
        if peak == 0:
            return 0.0
        threshold = clear_frac * peak
        # Only consider the decay after the peak is reached.
        seen_peak = False
        for t, n in self.active_ts:
            if n >= peak:
                seen_peak = True
            if seen_peak and n <= threshold:
                return t
        return self.active_ts[-1][0]
