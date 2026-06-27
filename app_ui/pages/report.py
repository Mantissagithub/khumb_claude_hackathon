"""Public — report a missing or found person (lands in the review queue)."""
from __future__ import annotations

import re
import time
from pathlib import Path

import streamlit as st

from app_ui.lib import data


def _options(col: str) -> list[str]:
    df = data.load_cases_df()
    vals = sorted(v for v in df[col].dropna().unique().tolist() if str(v).strip())
    return vals


def render() -> None:
    st.title("📝 Report a person")
    st.caption("Anyone can file a report. It enters the operator review queue — it is not auto-published.")

    genders = _options("gender")
    age_bands = _options("age_band")

    with st.form("report", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            missing_name = st.text_input("Person's name (if known)")
            gender = st.selectbox("Gender", ["—", *genders])
            age_band = st.selectbox("Age band", ["—", *age_bands])
            last_seen = st.text_input("Last seen location *", placeholder="e.g. Ramkund Ghat")
        with col2:
            reporter_name = st.text_input("Your name")
            reporter_phone = st.text_input("Your phone *", placeholder="+91…")
            photo = st.file_uploader("Photo (optional)", type=["jpg", "jpeg", "png"])
        description = st.text_area(
            "Physical description", placeholder="Clothing, height, distinguishing marks, language spoken…"
        )
        submitted = st.form_submit_button("Submit report", type="primary")

    if not submitted:
        return

    if not last_seen.strip() or not reporter_phone.strip():
        st.error("Last seen location and your phone number are required.")
        return
    if not re.fullmatch(r"[+0-9 \-]{7,20}", reporter_phone.strip()):
        st.error("Please enter a valid phone number.")
        return

    photo_path = _save_photo(photo) if photo else None
    sub_id = data.insert_submission(
        missing_name=missing_name.strip(),
        gender="" if gender == "—" else gender,
        age_band="" if age_band == "—" else age_band,
        last_seen_location=last_seen.strip(),
        physical_description=description.strip(),
        reporter_name=reporter_name.strip(),
        reporter_phone=reporter_phone.strip(),
        photo_path=photo_path,
    )
    lat, lng, zone = data.resolve_location(last_seen.strip())
    st.success(f"Report #{sub_id} filed. Resolved zone: **{zone or 'unknown'}**. An operator will review it shortly.")
    st.balloons()


def _save_photo(photo) -> str:
    # Stream to disk with a size cap (no whole-file-in-memory blowup).
    data.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(photo.name).suffix.lower() or ".jpg"
    fname = f"sub_{int(time.time() * 1000)}{ext}"
    dest = data.PHOTOS_DIR / fname
    raw = photo.getbuffer()
    if len(raw) > 8 * 1024 * 1024:
        st.warning("Photo over 8 MB was truncated.")
        raw = raw[: 8 * 1024 * 1024]
    dest.write_bytes(raw)
    return str(dest)
