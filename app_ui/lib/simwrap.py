"""Cached wrappers around the crowd-sim (sim/) and deployment planner (planning/).

The sim is numba-JIT + multi-thousand-step; we cache by scenario so re-rendering
the page does not re-simulate. Returns only plain/serialisable data so Streamlit's
@st.cache_data can memoise it.
"""
from __future__ import annotations

import streamlit as st


def scenarios() -> dict[str, str]:
    from sim.scenarios.run import SCENARIOS
    return {name: spec.notes for name, spec in SCENARIOS.items()}


@st.cache_data(show_spinner="Running crowd simulation…")
def run_sim(scenario: str, seed: int = 0) -> dict:
    from sim.scenarios import run_scenario

    sim, rec, report = run_scenario(scenario, seed=seed)
    return {
        "scenario": scenario,
        "peak_pressure": float(rec.global_peak_pressure),
        "separations": int(len(sim.separations)),
        "throughput": int(sim.arrived_count),
        "egress_s": float(rec.egress_time_s()),
        "notes": report.notes,
        "subzones": [
            {"name": s.name, "mean_density": float(s.mean_density), "peak_density": float(s.peak_density)}
            for s in rec.subzone_density()
        ],
        "pressure_points": [
            {"lat": float(p.lat), "lon": float(p.lng), "value": float(p.value), "t": float(p.t)}
            for p in report.pressure_points
        ],
        "separation_hotspots": [
            {"lat": float(h.lat), "lon": float(h.lng), "count": int(h.count)}
            for h in report.separation_hotspots
        ],
        "cctv_count": len(report.cctv_inventory),
        "units": [
            {"station": u.station, "lat": float(u.lat), "lon": float(u.lng), "available": int(u.available)}
            for u in report.available_units
        ],
    }


@st.cache_data(show_spinner="Planning deployment (this re-simulates 3 scenarios)…")
def run_plan(scenario: str, planner: str = "auto", seed: int = 0) -> dict:
    from planning.plan_bridge import run_bridge

    sc = run_bridge(scenario, planner, seed, None)
    d = sc.detail
    return {
        "scenario": d["scenario"],
        "planner": d["planner"],
        "plan_summary": d["plan_summary"],
        "wins": bool(sc.wins),
        "composite_planned": float(sc.composite_planned),
        "composite_baseline": float(sc.composite_baseline),
        "peak_pressure_baseline": float(sc.baseline.peak_pressure),
        "peak_pressure_planned": float(sc.planned.peak_pressure),
        "separations_baseline": int(sc.baseline.total_separations),
        "separations_planned": int(sc.planned.total_separations),
        "cctv_coverage_baseline": float(sc.baseline.cctv_coverage),
        "cctv_coverage_planned": float(sc.planned.cctv_coverage),
        "plan": d["plan"],
        "plan_coverage": d["plan_coverage"],
        "naive_coverage": d["naive_coverage"],
    }
