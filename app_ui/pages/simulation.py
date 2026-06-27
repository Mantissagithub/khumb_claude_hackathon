"""Crowd Simulation — run the Social-Force sim over the Ramkund ghat corridor."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_ui.lib import simwrap


def render() -> None:
    st.title("🧑‍🤝‍🧑 Crowd simulation")
    st.caption("Social-Force crowd model over the Ramkund ghat throat (numba-accelerated, cached).")

    scns = simwrap.scenarios()
    c1, c2 = st.columns([2, 1])
    scenario = c1.selectbox("Scenario", list(scns), format_func=lambda s: s.replace("_", " ").title())
    seed = c2.number_input("Seed", 0, 9999, 0)
    st.info(scns[scenario])

    if not st.button("Run simulation", type="primary"):
        return

    r = simwrap.run_sim(scenario, int(seed))

    m = st.columns(4)
    m[0].metric("Peak pressure", f"{r['peak_pressure']:.2f}")
    m[1].metric("Separations", r["separations"])
    m[2].metric("Throughput", r["throughput"])
    m[3].metric("Egress time", f"{r['egress_s']:.0f}s")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Sub-zone density (p/m²)")
        if r["subzones"]:
            sz = pd.DataFrame(r["subzones"]).set_index("name")[["mean_density", "peak_density"]]
            st.bar_chart(sz)
    with right:
        st.subheader("Pressure & separation hotspots")
        pts = []
        for p in r["pressure_points"]:
            pts.append({"lat": p["lat"], "lon": p["lon"]})
        for h in r["separation_hotspots"]:
            pts.append({"lat": h["lat"], "lon": h["lon"]})
        if pts:
            st.map(pd.DataFrame(pts))
        else:
            st.caption("No hotspots recorded for this scenario.")

    if r["pressure_points"]:
        with st.expander("Pressure points (raw)"):
            st.dataframe(pd.DataFrame(r["pressure_points"]), use_container_width=True)
