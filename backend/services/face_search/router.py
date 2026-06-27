"""HTTP layer for Feature 1 — face search. Thin wrapper over logic.py.

Endpoints (all under /api/face):
  GET  /health          backend + model status
  POST /search          frozen PLAN.md contract: image (+aadhaar) -> gallery matches + route
  POST /verify          image + supporting images -> "is it them?", confidence, why
  POST /search-footage  image + CCTV video clip   -> found?, timeline, annotated frame

Privacy by design: /verify and /search-footage ingest fresh images/video and
therefore REQUIRE consent_given=true; every call is audit-logged; biometrics and
raw uploads are never returned, and uploads are deleted after processing.
"""
from __future__ import annotations

import base64
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .logic import FaceSearchService

router = APIRouter(prefix="/api/face", tags=["face_search"])

CONSENT_MSG = ("consent_required: this processes a person's image/footage. "
               "Resubmit with consent_given=true (authorized operator + family/"
               "guardian consent on record).")


def _save(upload: UploadFile, tmpdir: str) -> str:
    path = os.path.join(tmpdir, os.path.basename(upload.filename or "upload"))
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


def _b64(path: str | None) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


@router.get("/health")
def health() -> dict:
    svc = FaceSearchService.get()
    return {"status": "ok",
            "embedding_backend": svc.pipe.embedder.backend,
            "detector_backend": svc.pipe.embedder._detector.backend
            if svc.pipe.embedder._detector else "n/a",
            "match_threshold": svc.thr,
            "note": "Decision-support tool; matches require human confirmation."}


@router.post("/search")
def search(image: UploadFile = File(...),
           aadhaar: UploadFile = File(None),
           consent_given: bool = Form(True),
           top_k: int = Form(5)) -> dict:
    """Frozen contract + an explainable verdict. Search a query face against the
    authorized camera gallery; if confidently found, route to nearest police."""
    svc = FaceSearchService.get()
    with tempfile.TemporaryDirectory() as td:
        qp = _save(image, td)
        res = svc.search_gallery(qp, top_k=top_k, consent=consent_given)
    return res


@router.post("/verify")
def verify(image: UploadFile = File(..., description="reference photo of the person"),
           support: list[UploadFile] = File(..., description="supporting images to compare"),
           consent_given: bool = Form(False)) -> dict:
    """Is the person in the reference photo present in the supporting images?"""
    if not consent_given:
        raise HTTPException(403, CONSENT_MSG)
    svc = FaceSearchService.get()
    with tempfile.TemporaryDirectory() as td:
        qp = _save(image, td)
        sps = [_save(s, td) for s in support]
        res = svc.verify(qp, sps, consent=consent_given)
        res["annotated_frame"] = _b64(res.pop("annotated_path", None))
    return res


@router.post("/search-footage")
def search_footage(image: UploadFile = File(..., description="reference photo"),
                   video: UploadFile = File(..., description="CCTV / video clip"),
                   consent_given: bool = Form(False),
                   max_frames: int = Form(60),
                   every_sec: float = Form(1.5)) -> dict:
    """Find the reference person inside a video clip; return when/where + frame."""
    if not consent_given:
        raise HTTPException(403, CONSENT_MSG)
    svc = FaceSearchService.get()
    with tempfile.TemporaryDirectory() as td:
        qp = _save(image, td)
        vp = _save(video, td)
        res = svc.search_footage(qp, vp, max_frames=max_frames,
                                 every_sec=every_sec, consent=consent_given)
        res["annotated_frame"] = _b64(res.pop("annotated_path", None))
    return res
