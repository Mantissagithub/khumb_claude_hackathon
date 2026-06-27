"""Dashboard — registry overview + live operations map."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_ui.lib import data


def render() -> None:
    st.title("🪔 KumbhSeva — Reunification & Crowd-Safety Console")
    st.caption("Nashik / Trimbakeshwar Kumbh 2027 · unified Streamlit app over the combined backend")

    a = data.analytics()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Registry cases", f"{a['total_cases']:,}")
    c2.metric("Active (searching)", f"{a['active']:,}")
    c3.metric("Reunited", f"{a['reunited']:,}")
    c4.metric("Matched", f"{a['matched']:,}")
    c5.metric("Pending submissions", f"{a['pending_submissions']:,}")

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Cases by status")
        s = pd.Series(a["by_status"]).sort_values(ascending=False)
        st.bar_chart(s, color="#d97706")
    with right:
        st.subheader("Top active zones")
        if a["top_zones"]:
            st.bar_chart(pd.Series(a["top_zones"]).sort_values(ascending=False), color="#2563eb")
        else:
            st.info("No active cases with a resolved zone.")

    st.divider()
    st.subheader("Operations map")
    _map()


def _map() -> None:
    try:
        import pydeck as pdk
    except Exception:
        _fallback_map()
        return

    df = data.load_cases_df()
    geo = data.geo_reference()

    show = st.multiselect(
        "Layers",
        ["Active cases", "CCTV", "Police", "Chokepoints"],
        default=["Active cases", "CCTV"],
    )

    layers = []
    if "Active cases" in show:
        cases = df[(df["status"] == "Active") & df["lat"].notna()][["lat", "lng"]].rename(columns={"lng": "lon"})
        cases = cases.sample(min(len(cases), 1500), random_state=0) if len(cases) else cases
        layers.append(pdk.Layer("ScatterplotLayer", data=cases, get_position="[lon, lat]",
                                get_fill_color="[217, 119, 6, 120]", get_radius=40, pickable=False))
    if "CCTV" in show and len(geo["cameras"]):
        layers.append(pdk.Layer("ScatterplotLayer", data=geo["cameras"], get_position="[lon, lat]",
                                get_fill_color="[37, 99, 235, 160]", get_radius=25))
    if "Police" in show and len(geo["police"]):
        layers.append(pdk.Layer("ScatterplotLayer", data=geo["police"], get_position="[lon, lat]",
                                get_fill_color="[22, 163, 74, 220]", get_radius=70))
    if "Chokepoints" in show and len(geo["chokepoints"]):
        layers.append(pdk.Layer("ScatterplotLayer", data=geo["chokepoints"], get_position="[lon, lat]",
                                get_fill_color="[220, 38, 38, 200]", get_radius=60))

    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=19.99, longitude=73.79, zoom=11, pitch=0),
        layers=layers,
    ))
    st.caption("🟠 active cases · 🔵 CCTV · 🟢 police · 🔴 chokepoints/parking")


def _fallback_map() -> None:
    df = data.load_cases_df()
    pts = df[(df["status"] == "Active") & df["lat"].notna()][["lat", "lng"]].rename(columns={"lng": "lon"})
    if len(pts):
        st.map(pts.sample(min(len(pts), 1500), random_state=0))
