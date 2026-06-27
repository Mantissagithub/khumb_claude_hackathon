"""Deployment Planning — sim → Claude/heuristic plan → re-sim → scorecard."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from app_ui.lib import simwrap


def render() -> None:
    st.title("🚓 Deployment planning")
    st.caption("Closed loop: predict the crowd, plan police/CCTV/barriers, re-simulate, and score vs naive-uniform.")

    have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if have_key:
        st.success("ANTHROPIC_API_KEY detected — 'auto'/'claude' will use live Claude planning.")
    else:
        st.warning("No ANTHROPIC_API_KEY — planner falls back to the local heuristic (still fully runnable).")

    scns = simwrap.scenarios()
    c1, c2, c3 = st.columns(3)
    scenario = c1.selectbox("Scenario", list(scns), format_func=lambda s: s.replace("_", " ").title())
    planner = c2.selectbox("Planner", ["auto", "heuristic", "claude"])
    seed = c3.number_input("Seed", 0, 9999, 0)

    if not st.button("Plan & evaluate", type="primary"):
        return

    try:
        r = simwrap.run_plan(scenario, planner, int(seed))
    except Exception as e:
        st.error(f"Planner failed: {type(e).__name__}: {e}")
        return

    verdict = "✅ Plan beats naive-uniform" if r["wins"] else "➖ No improvement over naive-uniform"
    st.subheader(f"{verdict}  ·  planner: {r['planner']}")
    st.write(f"**Plan:** {r['plan_summary']}")

    m = st.columns(3)
    m[0].metric("Composite", f"{r['composite_planned']:.3f}",
                delta=f"{r['composite_planned'] - r['composite_baseline']:+.3f}")
    m[1].metric("Peak pressure", f"{r['peak_pressure_planned']:.2f}",
                delta=f"{r['peak_pressure_planned'] - r['peak_pressure_baseline']:+.2f}", delta_color="inverse")
    m[2].metric("Separations", r["separations_planned"],
                delta=r["separations_planned"] - r["separations_baseline"], delta_color="inverse")

    st.divider()
    plan = r["plan"]
    forces = plan.get("force_allocations") or plan.get("forces") or []
    if forces:
        st.subheader("Force allocations")
        st.dataframe(pd.DataFrame(forces), use_container_width=True)
        pts = pd.DataFrame([{"lat": f.get("lat"), "lon": f.get("lng")} for f in forces
                            if f.get("lat") and f.get("lng")])
        if len(pts):
            st.map(pts)

    cctv = plan.get("cctv_reaims") or plan.get("cctv") or []
    if cctv:
        with st.expander("CCTV re-aims"):
            st.dataframe(pd.DataFrame(cctv), use_container_width=True)

    with st.expander("Full plan + coverage (raw)"):
        st.json({"plan": plan, "plan_coverage": r["plan_coverage"], "naive_coverage": r["naive_coverage"]})
