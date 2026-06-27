"""Operator / Admin — review queue: match, confirm, promote, reject, reunite."""
from __future__ import annotations

import os

import streamlit as st

from app_ui.lib import data, matching


def render() -> None:
    role = st.session_state.get("role", "Operator")
    staff_id = data.staff_id_for_role(role)
    st.title("🗂️ Review queue")
    st.caption(f"Signed in as **{role}**. Public reports await triage here.")

    subs = data.load_submissions_df()
    if not len(subs):
        st.info("No submissions yet. File one from **Report a person** to see the workflow.")
        _reunite_panel()
        return

    flt = st.radio("Show", ["pending", "reviewing", "all"], horizontal=True)
    view = subs if flt == "all" else subs[subs["review_status"] == flt]
    st.write(f"{len(view)} submission(s)")

    for _, sub in view.iterrows():
        sid = int(sub["id"])
        title = f"#{sid} · {sub['missing_name'] or '(no name)'} · {sub['review_status']}"
        with st.expander(title, expanded=(flt != "all")):
            cols = st.columns([2, 1])
            with cols[0]:
                st.write(f"**Gender:** {sub['gender'] or '—'} · **Age:** {sub['age_band'] or '—'}")
                st.write(f"📍 {sub['last_seen_location'] or '—'}  ·  zone {sub['zone'] or '—'}")
                if sub["physical_description"]:
                    st.write(sub["physical_description"])
                st.caption(f"Reporter: {sub['reporter_name'] or '—'} ({sub['reporter_phone']})")
            with cols[1]:
                if sub["photo_path"] and os.path.exists(sub["photo_path"]):
                    st.image(sub["photo_path"], use_container_width=True)

            b1, b2, b3 = st.columns(3)
            if b1.button("🔎 Find matches", key=f"m{sid}"):
                data.set_reviewing(sid, staff_id)
                st.session_state[f"matches_{sid}"] = matching.search(
                    query_text=sub["physical_description"] or "",
                    name=sub["missing_name"] or "",
                    gender=sub["gender"] or "",
                    age_band=sub["age_band"] or "",
                    zone=sub["zone"] or "",
                    top_n=5,
                )
            if b2.button("➕ Promote to new case", key=f"p{sid}"):
                cid = data.promote_submission(sid, staff_id)
                st.success(f"Created case {cid}")
                st.rerun()
            if b3.button("🚫 Reject", key=f"r{sid}"):
                data.reject_submission(sid, staff_id, "rejected by reviewer")
                st.rerun()

            cands = st.session_state.get(f"matches_{sid}")
            if cands is not None:
                if not cands:
                    st.info("No candidate matches found.")
                for c in cands:
                    cc = st.columns([4, 1])
                    cc[0].markdown(
                        f"**{c['name'] or '(no name)'}** `{c['case_id']}` — {c['score']:.0%} · {c['reason']}"
                    )
                    if cc[1].button("Confirm", key=f"c{sid}_{c['case_id']}"):
                        data.confirm_match(sid, c["case_id"], staff_id, "confirmed from queue")
                        st.success(f"Matched submission #{sid} → {c['case_id']}")
                        st.session_state.pop(f"matches_{sid}", None)
                        st.rerun()

    _reunite_panel()


def _reunite_panel() -> None:
    st.divider()
    st.subheader("✅ Mark a case reunited")
    cid = st.text_input("Case ID", placeholder="KMP-2027-00001 or PUB-00001")
    if st.button("Mark reunited") and cid.strip():
        df = data.load_cases_df()
        if cid.strip() in set(df["case_id"]):
            data.reunite_case(cid.strip())
            st.success(f"{cid.strip()} marked Reunited.")
            st.rerun()
        else:
            st.error("No such case ID.")
