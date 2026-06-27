"""Score a deployment: coverage of predicted hotspots + re-simulated physics.

The composite is coverage-centred (AGENTS.md §6: "better than naive uniform
placement on a coverage metric"), with the re-simulation's peak pressure and
separation count folded in as supporting evidence. Higher composite = better.
"""

from __future__ import annotations

from shared.schema import DeploymentPlan, Metrics, SituationReport
from sim.controllables import POLICE_PARAMS, Deployment
from sim.geometry import Corridor
from sim.io import corridor_cameras
from sim.metrics import cctv_coverage
from sim.scenarios import run_scenario

_UNIT_RADIUS = {"constable": POLICE_PARAMS["constable"].control_radius,
                "squad": POLICE_PARAMS["squad"].control_radius,
                "barricade": 8.0}


def _force_coverage(corridor: Corridor, report: SituationReport, plan: DeploymentPlan) -> float:
    """Pressure-weighted fraction of top pressure points within a unit's radius."""
    pts = report.pressure_points
    if not pts:
        return 1.0
    proj = corridor.proj
    units = [(proj.to_xy(f.lng, f.lat), _UNIT_RADIUS.get(f.unit_type, 2.5)) for f in plan.force_allocations]
    wsum = sum(p.value for p in pts) or 1.0
    covered = 0.0
    for p in pts:
        px, py = proj.to_xy(p.lng, p.lat)
        if any((px - ux) ** 2 + (py - uy) ** 2 <= r * r for (ux, uy), r in units):
            covered += p.value
    return covered / wsum


def _helpdesk_coverage(corridor: Corridor, report: SituationReport, plan: DeploymentPlan,
                       reach_m: float = 15.0) -> float:
    """Count-weighted fraction of separation hotspots within reach of a help desk."""
    hots = report.separation_hotspots
    if not hots:
        return 1.0
    proj = corridor.proj
    desks = [proj.to_xy(d.lng, d.lat) for d in plan.helpdesks]
    if not desks:
        return 0.0
    wsum = sum(h.count for h in hots) or 1.0
    covered = 0.0
    for h in hots:
        hx, hy = proj.to_xy(h.lng, h.lat)
        if any((hx - dx) ** 2 + (hy - dy) ** 2 <= reach_m * reach_m for dx, dy in desks):
            covered += h.count
    return covered / wsum


def score_deployment(scenario: str, corridor: Corridor, base_report: SituationReport,
                     plan: DeploymentPlan, seed: int = 0) -> tuple[Metrics, dict]:
    """Re-simulate the scenario under ``plan`` and measure outcome + coverage."""
    dep = Deployment(corridor, plan)
    sim, rec, _ = run_scenario(scenario, deployment=dep, seed=seed)

    cameras = dep.apply_cctv(corridor_cameras(corridor))
    cov = cctv_coverage(rec, cameras)
    metrics = Metrics(
        peak_pressure=rec.global_peak_pressure,
        total_separations=len(sim.separations),
        cctv_coverage=cov["coverage"],
        egress_time_s=rec.egress_time_s(),
    )
    detail = {
        "force_coverage": _force_coverage(corridor, base_report, plan),
        "helpdesk_coverage": _helpdesk_coverage(corridor, base_report, plan),
        "cctv_blindspots": len(cov["blindspots"]),
    }
    return metrics, detail


# Composite weights. Coverage of the predicted hotspots (force/CCTV/help-desk) is
# the AGENTS.md §6 criterion; separation reduction is the mission outcome (family
# reunification), so it carries real weight alongside peak crowd pressure.
_W = {"force": 0.20, "cctv": 0.30, "helpdesk": 0.10, "pressure": 0.15, "separations": 0.25}


def composite(metrics: Metrics, detail: dict, refs: dict) -> float:
    """Blend coverage (higher=better) with normalised physics (lower=better)."""
    p_ref = max(refs.get("peak_pressure", 1.0), 1e-6)
    s_ref = max(refs.get("total_separations", 1), 1)
    pressure_term = max(0.0, 1.0 - metrics.peak_pressure / p_ref)
    sep_term = max(0.0, 1.0 - metrics.total_separations / s_ref)
    return (
        _W["force"] * detail["force_coverage"]
        + _W["cctv"] * metrics.cctv_coverage
        + _W["helpdesk"] * detail["helpdesk_coverage"]
        + _W["pressure"] * pressure_term
        + _W["separations"] * sep_term
    )
