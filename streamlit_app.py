"""KumbhSeva — unified Streamlit app.

One front-end over the whole combined backend: the reunification registry
(report → review → match → reunite) and the crowd-safety tools (Social-Force
simulation + Claude/heuristic deployment planning).

Run:  ./venv/bin/streamlit run streamlit_app.py
      (or)  streamlit run streamlit_app.py
"""
from __future__ import annotations

import streamlit as st

from app_ui.lib import bootstrap

bootstrap.init()

st.set_page_config(page_title="KumbhSeva", page_icon="🪔", layout="wide")

from app_ui.pages import home, planning, report, review, search, simulation  # noqa: E402

with st.sidebar:
    st.markdown("## 🪔 KumbhSeva")
    role = st.selectbox("Role", ["Public", "Operator", "Admin"], key="role")
    st.caption("Switch to Operator/Admin to unlock the review queue and crowd-safety tools.")
    st.divider()

reunification = [
    st.Page(home.render, title="Dashboard", icon="📊", url_path="dashboard", default=True),
    st.Page(report.render, title="Report a person", icon="📝", url_path="report"),
    st.Page(search.render, title="Search & Match", icon="🔍", url_path="search"),
]
if role in ("Operator", "Admin"):
    reunification.append(st.Page(review.render, title="Review queue", icon="🗂️", url_path="review"))

groups: dict[str, list] = {"Reunification": reunification}
if role in ("Operator", "Admin"):
    groups["Crowd safety"] = [
        st.Page(simulation.render, title="Crowd simulation", icon="🧑‍🤝‍🧑", url_path="simulation"),
        st.Page(planning.render, title="Deployment planning", icon="🚓", url_path="planning"),
    ]

st.navigation(groups).run()
