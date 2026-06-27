"""Search & Match — query the active registry with the fast cached matcher."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app_ui.lib import data, matching


def _opts(col: str) -> list[str]:
    df = data.load_cases_df()
    return sorted(v for v in df[col].dropna().unique().tolist() if str(v).strip())


def render() -> None:
    st.title("🔍 Search & Match")
    st.caption("Ranked candidates from the active registry — candidate-blocked + cached for speed.")

    with st.form("search"):
        name = st.text_input("Name")
        desc = st.text_area("Description / keywords", placeholder="saffron kurta, rudraksha mala, elderly…")
        c1, c2, c3, c4 = st.columns(4)
        gender = c1.selectbox("Gender", ["Any", *_opts("gender")])
        age_band = c2.selectbox("Age band", ["Any", *_opts("age_band")])
        zone = c3.selectbox("Zone", ["Any", *_opts("zone")])
        top_n = c4.slider("Results", 5, 30, 10)
        go = st.form_submit_button("Search", type="primary")

    if not go:
        return
    if not (name.strip() or desc.strip() or gender != "Any" or zone != "Any"):
        st.warning("Enter a name, description, or pick at least one attribute.")
        return

    results = matching.search(
        query_text=desc, name=name,
        gender="" if gender == "Any" else gender,
        age_band="" if age_band == "Any" else age_band,
        zone="" if zone == "Any" else zone,
        top_n=top_n,
    )
    if not results:
        st.info("No candidates matched. Try loosening the attribute filters.")
        return

    st.success(f"Top {len(results)} candidates")
    for r in results:
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{r['name'] or '(no name)'}**  ·  `{r['case_id']}`")
            top[1].progress(min(r["score"], 1.0), text=f"{r['score']:.0%}")
            meta = " · ".join(x for x in [r["gender"], r["age_band"], r["zone"], r["language"]] if x)
            st.caption(meta)
            if r["last_seen_location"]:
                st.write(f"📍 {r['last_seen_location']}")
            if r["physical_description"]:
                st.write(r["physical_description"])
            st.caption(f"Why: {r['reason']}")

    pts = pd.DataFrame(
        [{"lat": r["lat"], "lon": r["lng"]} for r in results if r["lat"] and r["lng"]]
    )
    if len(pts):
        st.subheader("Candidate locations")
        st.map(pts)
