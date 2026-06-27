"""Two reference planners:

* ``heuristic_plan``  — a *targeted* plan derived directly from the situation
  report (the keyless fallback for the closed loop; also a sanity baseline for
  what a good plan looks like).
* ``naive_uniform_plan`` — the same resource *budget* as a given plan, but spread
  uniformly and blindly. This is the "naive uniform placement" AGENTS.md §6 asks
  us to beat.

Both return a ``shared.schema.DeploymentPlan`` in geo coordinates.
"""

from __future__ import annotations

import math

from shared.schema import (
    BarrierPlan,
    CctvReaim,
    DeploymentPlan,
    DispatchRoute,
    ForceAllocation,
    HelpDesk,
    SituationReport,
)
from sim.geometry import Corridor


def _heading_deg(from_lng, from_lat, to_lng, to_lat, proj) -> float:
    fx, fy = proj.to_xy(from_lng, from_lat)
    tx, ty = proj.to_xy(to_lng, to_lat)
    return math.degrees(math.atan2(ty - fy, tx - fx))


def _gate(corridor: Corridor, y: float, cap: float) -> BarrierPlan:
    half = corridor.width_at(y) / 2.0 - 0.3
    l1 = corridor.proj.to_lnglat(-half, y)
    l2 = corridor.proj.to_lnglat(half, y)
    return BarrierPlan(l1[0], l1[1], l2[0], l2[1], throughput_cap=cap, rationale=f"meter at y={y:.0f} m")


def heuristic_plan(report: SituationReport, corridor: Corridor) -> DeploymentPlan:
    cfg = corridor.cfg
    proj = corridor.proj
    pts = report.pressure_points
    hots = report.separation_hotspots
    cams = report.cctv_inventory

    # Meter upstream of the throat, in the widening where held crowd has room.
    gate_y = cfg.throat_len_m + 0.4 * (cfg.length_m - cfg.throat_len_m)
    barriers = [_gate(corridor, gate_y, cap=3.0)]

    # Re-aim each nearest camera at the top pressure points / hotspots.
    targets = pts[:4] + hots[:2]
    reaims: list[CctvReaim] = []
    used = set()
    for tgt in targets:
        best, bestd = None, 1e18
        for c in cams:
            if c.camera_id in used:
                continue
            cx, cy = proj.to_xy(c.lng, c.lat)
            tx, ty = proj.to_xy(tgt.lng, tgt.lat)
            d = (cx - tx) ** 2 + (cy - ty) ** 2
            if d < bestd:
                best, bestd = c, d
        if best is not None:
            used.add(best.camera_id)
            reaims.append(CctvReaim(best.camera_id,
                                    _heading_deg(best.lng, best.lat, tgt.lng, tgt.lat, proj),
                                    "cover predicted high-pressure / separation point"))

    # Squads at the two highest-pressure points; a constable at the third.
    forces: list[ForceAllocation] = []
    for i, p in enumerate(pts[:3]):
        utype = "squad" if i < 2 else "constable"
        forces.append(ForceAllocation(utype, p.lng, p.lat, "organize high-pressure zone"))

    # Help desks at the worst separation hotspots.
    desks = [HelpDesk(h.lng, h.lat, "Kho-Ya-Paya desk at separation hotspot") for h in hots[:3]]

    # Nearest-unit dispatch route from the closest station to the top pressure point.
    routes: list[DispatchRoute] = []
    if pts and report.available_units:
        tgt = pts[0]
        st = min(report.available_units,
                 key=lambda u: (u.lng - tgt.lng) ** 2 + (u.lat - tgt.lat) ** 2)
        routes.append(DispatchRoute(st.station, [[st.lng, st.lat], [tgt.lng, tgt.lat]],
                                    purpose="dispatch", rationale="nearest unit to the danger zone"))

    return DeploymentPlan(
        summary="Targeted: meter above the throat, aim CCTV at pressure/separation points, "
                "site help desks at hotspots, dispatch the nearest unit.",
        force_allocations=forces, cctv_reaims=reaims, barriers=barriers, helpdesks=desks, routes=routes,
    )


def naive_uniform_plan(report: SituationReport, corridor: Corridor, like: DeploymentPlan) -> DeploymentPlan:
    """Equal budget to ``like``, but placed uniformly along the corridor centreline
    and with cameras left at their default aim (no targeting)."""
    cfg = corridor.cfg
    proj = corridor.proj
    n_force = len(like.force_allocations)
    n_desk = len(like.helpdesks)
    n_gate = len(like.barriers)

    def uniform_ys(k: int) -> list[float]:
        if k <= 0:
            return []
        return [cfg.length_m * (i + 1) / (k + 1) for i in range(k)]

    forces = []
    for ftype, y in zip([f.unit_type for f in like.force_allocations], uniform_ys(n_force)):
        lng, lat = proj.to_lnglat(0.0, y)
        forces.append(ForceAllocation(ftype, lng, lat, "uniform placement"))

    desks = []
    for y in uniform_ys(n_desk):
        lng, lat = proj.to_lnglat(0.0, y)
        desks.append(HelpDesk(lng, lat, "uniform placement"))

    barriers = [_gate(corridor, y, cap=3.0) for y in uniform_ys(n_gate)]

    # No re-aims: cameras stay at their default heading (the blind baseline).
    return DeploymentPlan(
        summary="Naive uniform: equal resources spread evenly; cameras left at default aim.",
        force_allocations=forces, cctv_reaims=[], barriers=barriers, helpdesks=desks, routes=[],
    )
