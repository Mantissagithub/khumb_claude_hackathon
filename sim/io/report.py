"""Build the SituationReport the planning pillar (and Claude) consume.

Pulls the real CCTV inventory and police stations from ``shared.loaders``, the
crowd layers from the :class:`MetricsRecorder`, and packages them into the frozen
``shared.schema.SituationReport`` contract.
"""

from __future__ import annotations

import csv
from pathlib import Path

from shared.geo import haversine_m
from shared.loaders import load_cameras, load_police_stations
from shared.schema import CameraState, SituationReport, UnitAvailability
from sim.geometry import Corridor
from sim.metrics import MetricsRecorder


def corridor_cameras(corridor: Corridor, default_range_m: float = 55.0,
                     default_fov_deg: float = 45.0, near_radius_m: float = 150.0) -> list[CameraState]:
    """The CCTV inventory overlooking this corridor.

    Grounding caveat: the dataset's 1,280 cameras are city-wide, and for Ramkund
    the nearest is ~1.6 km away — the provided CCTV layer does not cover this ghat.
    A real ghat deployment installs its own masts, so we model the corridor's own
    cameras (mounted along both edges of the approach) as the re-aimable inventory.
    If the dataset *does* have cameras within ``near_radius_m`` of a corridor
    (true for other sites), those are used instead.

    Cameras default to aiming due east (90°) — an arbitrary un-tuned heading the
    plan is expected to improve by aiming down the approach at the danger zones.
    """
    a_lng, a_lat = corridor.cfg.anchor_lng, corridor.cfg.anchor_lat
    near = [c for c in load_cameras() if haversine_m(a_lng, a_lat, c.lng, c.lat) <= near_radius_m]
    if near:
        return [CameraState(c.camera_id, c.lng, c.lat, 90.0, default_fov_deg, default_range_m)
                for c in near]

    # PTZ cameras on poles in the upper plaza, overlooking the approach down to the
    # water (the real ghat layout). Narrow cones: a camera sees only where it is
    # aimed. Their default heading (90 deg = up-approach) watches the incoming crowd,
    # leaving the downstream ghat throat BLIND until the plan re-aims them down at the
    # predicted danger -- so coverage of the crush zone is decided by sim-informed
    # aiming, not by mere presence.
    proj = corridor.proj
    cfg = corridor.cfg
    depths = [cfg.length_m * 0.78, cfg.length_m * 0.95]
    out: list[CameraState] = []
    for di, y in enumerate(depths):
        edge = corridor.width_at(y) / 2.0 + 1.0
        for side, x in (("L", -edge), ("R", edge)):
            lng, lat = proj.to_lnglat(x, y)
            out.append(CameraState(f"GHAT-{di+1}{side}", lng, lat, 90.0, default_fov_deg, default_range_m))
    return out


def nearby_units(corridor: Corridor, pool: int = 24) -> list[UnitAvailability]:
    """Notional deployable units per police station, weighted toward the corridor.

    A fixed force ``pool`` is split across the 14 real stations by inverse distance
    to the corridor — nearer stations can spare more to this site.
    """
    stations = load_police_stations()
    a_lng, a_lat = corridor.cfg.anchor_lng, corridor.cfg.anchor_lat
    weights = []
    for s in stations:
        d_km = haversine_m(a_lng, a_lat, s.lng, s.lat) / 1000.0
        weights.append(1.0 / (1.0 + d_km))
    total = sum(weights)
    out = []
    for s, w in zip(stations, weights):
        out.append(
            UnitAvailability(
                station=s.name, lng=s.lng, lat=s.lat,
                available=max(1, round(pool * w / total)),
            )
        )
    return out


def build_situation_report(
    scenario: str,
    corridor: Corridor,
    rec: MetricsRecorder,
    cameras: list[CameraState],
    duration_s: float,
    notes: str = "",
) -> SituationReport:
    return SituationReport(
        scenario=scenario,
        corridor_id=corridor.cfg.corridor_id,
        t_window_s=duration_s,
        pressure_points=rec.top_pressure_points(k=8),
        separation_hotspots=rec.separation_hotspots(k=6),
        density_summary=rec.subzone_density(),
        available_units=nearby_units(corridor),
        cctv_inventory=cameras,
        notes=notes,
    )


def write_density_csv(rec: MetricsRecorder, path: str | Path) -> None:
    """Dump the peak-pressure layer as a lng,lat,peak_pressure,mean_density grid."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mean_d = rec.mean_density
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["lng", "lat", "peak_pressure", "mean_density"])
        for iy in range(rec.ny):
            for ix in range(rec.nx):
                if rec.peak_pressure[iy, ix] <= 0 and mean_d[iy, ix] <= 0:
                    continue
                lng, lat = rec._cell_to_lnglat(iy, ix)
                w.writerow([f"{lng:.6f}", f"{lat:.6f}",
                            f"{rec.peak_pressure[iy, ix]:.4f}", f"{mean_d[iy, ix]:.4f}"])
