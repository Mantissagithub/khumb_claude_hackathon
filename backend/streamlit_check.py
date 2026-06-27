"""Streamlit checking UI for the Sangam face-search API.

Purpose: a quick visual harness to confirm the backend works and to SEE its
output — not a production UI. It calls the running FastAPI service over HTTP.

Run (backend must be up on :8000):
    streamlit run backend/streamlit_check.py
"""
import base64
import io

import requests
import streamlit as st

st.set_page_config(page_title="Sangam — Face Search Checker", layout="wide")

# --- sidebar: backend + health --------------------------------------------
st.sidebar.title("⚙️ Backend")
API = st.sidebar.text_input("API base URL", "http://127.0.0.1:8000")
consent = st.sidebar.checkbox("consent_given (required for verify/footage)", value=True)

if st.sidebar.button("Check health"):
    try:
        st.sidebar.write("ping:", requests.get(f"{API}/api/ping", timeout=5).json())
        st.sidebar.write("face:", requests.get(f"{API}/api/face/health", timeout=120).json())
    except Exception as e:
        st.sidebar.error(f"backend unreachable: {e}")

st.title("🔍 Sangam Face Search — checking UI")
st.caption("Upload a reference photo + supporting images or a video clip. "
           "The service replies: is it them, how confident, and why. "
           "Decision-support only — a human confirms.")


# --- helpers ---------------------------------------------------------------
def _uf(upload):
    return (upload.name, io.BytesIO(upload.getvalue()),
            upload.type or "application/octet-stream")


def show_annotated(resp):
    b64 = resp.get("annotated_frame")
    if b64:
        st.image(base64.b64decode(b64.split(",", 1)[-1]), caption="Located face",
                 use_container_width=True)


def show_verdict(resp):
    band = resp.get("band", "")
    color = {"STRONG": "green", "LIKELY": "green", "POSSIBLE": "orange",
             "NO_MATCH": "red"}.get(band, "gray")
    c1, c2 = st.columns([2, 1])
    c1.markdown(f"### :{color}[{resp.get('verdict', '—')}]")
    c2.metric("Confidence", f"{resp.get('confidence_pct', 0)} %")
    if resp.get("is_match") is not None:
        c1.write(f"**is_match:** `{resp.get('is_match')}`  ·  "
                 f"**band:** `{band}`  ·  **score:** `{resp.get('score')}`")
    for r in resp.get("reasons", []):
        st.write("• " + r)


tab1, tab2, tab3 = st.tabs(["✅ Verify (image vs images)",
                            "🎞️ Search footage (image vs video)",
                            "🗂️ Gallery search"])

# --- tab 1: verify ---------------------------------------------------------
with tab1:
    ref = st.file_uploader("Reference photo (the person you're looking for)",
                           type=["jpg", "jpeg", "png"], key="v_ref")
    sup = st.file_uploader("Supporting images to compare",
                           type=["jpg", "jpeg", "png"], accept_multiple_files=True,
                           key="v_sup")
    if ref:
        st.image(ref, width=180, caption="reference")
    if st.button("Run verify", type="primary", disabled=not (ref and sup)):
        files = [("image", _uf(ref))] + [("support", _uf(s)) for s in sup]
        with st.spinner("matching..."):
            r = requests.post(f"{API}/api/face/verify", files=files,
                              data={"consent_given": str(consent).lower()}, timeout=300)
        if r.status_code == 403:
            st.error(r.json().get("detail"))
        else:
            resp = r.json()
            show_verdict(resp)
            a, b = st.columns(2)
            with a:
                show_annotated(resp)
            with b:
                if resp.get("per_image"):
                    st.write("**Per-image scores**")
                    st.dataframe(resp["per_image"], use_container_width=True)
            with st.expander("raw JSON output"):
                st.json(resp)

# --- tab 2: footage --------------------------------------------------------
with tab2:
    ref2 = st.file_uploader("Reference photo", type=["jpg", "jpeg", "png"], key="f_ref")
    vid = st.file_uploader("CCTV / video clip", type=["mp4", "webm", "ogv", "avi", "mov"],
                           key="f_vid")
    mf = st.slider("max frames sampled", 10, 120, 60, 10)
    es = st.slider("seconds between sampled frames", 0.5, 5.0, 1.5, 0.5)
    if st.button("Search footage", type="primary", disabled=not (ref2 and vid)):
        files = [("image", _uf(ref2)), ("video", _uf(vid))]
        with st.spinner("sampling frames + matching... (first run loads the model)"):
            r = requests.post(f"{API}/api/face/search-footage", files=files,
                              data={"consent_given": str(consent).lower(),
                                    "max_frames": mf, "every_sec": es}, timeout=600)
        if r.status_code == 403:
            st.error(r.json().get("detail"))
        else:
            resp = r.json()
            show_verdict(resp)
            st.write(f"**Frames sampled:** {resp.get('frames_sampled')}  ·  "
                     f"**Confident appearances (s):** {resp.get('appearances_sec')}")
            show_annotated(resp)
            with st.expander("raw JSON output"):
                st.json(resp)

# --- tab 3: gallery --------------------------------------------------------
with tab3:
    st.caption("Searches the reference face against the stand-in camera gallery "
               "(FACE_GALLERY_DIR). If confidently found, routes to nearest police.")
    ref3 = st.file_uploader("Reference photo", type=["jpg", "jpeg", "png"], key="g_ref")
    if st.button("Search gallery", type="primary", disabled=not ref3):
        with st.spinner("searching gallery..."):
            r = requests.post(f"{API}/api/face/search",
                              files=[("image", _uf(ref3))],
                              data={"consent_given": str(consent).lower()}, timeout=300)
        resp = r.json()
        show_verdict(resp)
        if resp.get("route"):
            st.success(f"Route → {resp['route']['to']}")
            for s in resp["route"]["steps"]:
                st.write("• " + s)
        if resp.get("matches"):
            st.write("**Matches**")
            st.dataframe(resp["matches"], use_container_width=True)
        with st.expander("raw JSON output"):
            st.json(resp)
