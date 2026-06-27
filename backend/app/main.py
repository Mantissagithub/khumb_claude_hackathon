"""Sangam API — the two features wired end to end.

Feature 1: Face + Cloth matching
  POST /reports/found  and  POST /reports/missing  accept an optional photo.
  On intake we compute a face embedding + a cloth colour signature, store the
  report, and immediately return ranked matches against the opposite-type
  reports AND the government registry, each with a location.

Feature 2: Cross-language voice matching
  POST /voice/query  accepts an audio clip in any language. We transcribe +
  translate to English, parse a structured query, and return ranked matches.

Run:  uvicorn app.main:app --reload   (from the backend/ directory)
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import config, data_loader
from .matching import cloth, face, voice
from .matching.engine import MatchEngine
from .models import Report
from .store import Store

app = FastAPI(title="Sangam — Missing Persons Matching", version="0.1.0")

# Built once at startup.
GEO: data_loader.GeoContext
STORE: Store
ENGINE: MatchEngine


@app.on_event("startup")
def _startup() -> None:
    global GEO, STORE, ENGINE
    GEO = data_loader.GeoContext.build()
    STORE = Store(data_loader.load_government_registry())
    ENGINE = MatchEngine(STORE, GEO)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save_photo(report_id: str, photo: UploadFile) -> str:
    dest = config.UPLOAD_DIR / f"{report_id}_{photo.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(photo.file, f)
    return str(dest)


def _register(type_: str, fields: dict, photo: Optional[UploadFile]) -> Report:
    rid = STORE.new_id(type_)
    rep = Report(id=rid, source="live", type=type_, created_at=_now(), **fields)
    if photo is not None:
        rep.photo_path = _save_photo(rid, photo)
        if face.available:
            rep.face_embedding = face.embed(rep.photo_path)
        if cloth.available:
            rep.cloth_signature = cloth.signature(rep.photo_path)
    return STORE.add(rep)


# --- health / stats --------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "backends": {
            "face": face.backend_name,
            "cloth": "pillow+numpy" if cloth.available else "none",
            "voice": voice.backend_name,
        },
    }


@app.get("/stats")
def stats() -> dict:
    return STORE.stats()


# --- Feature 1: face + cloth intake & match --------------------------------
def _intake(type_: str, name, gender, age_band, state, district, language,
            last_seen_location, reporter_mobile, physical_description,
            lat, lng, reporting_center, photo) -> dict:
    fields = dict(
        name=name or "", gender=gender or "", age_band=age_band or "",
        state=state or "", district=district or "", language=language or "",
        last_seen_location=last_seen_location or "",
        reporter_mobile=reporter_mobile or "",
        physical_description=physical_description or "",
        reporting_center=reporting_center or "",
        lat=lat, lng=lng,
    )
    rep = _register(type_, fields, photo)
    matches = ENGINE.match(rep, scope="all")
    return {
        "report": rep.public_dict(),
        "report_location": GEO.enrich(rep.lat, rep.lng, rep.last_seen_location),
        "match_count": len(matches),
        "matches": matches,
        "note": "Matches are suggestions for an operator to confirm — nothing is auto-merged.",
    }


@app.post("/reports/found")
def report_found(
    name: str = Form(""), gender: str = Form(""), age_band: str = Form(""),
    state: str = Form(""), district: str = Form(""), language: str = Form(""),
    last_seen_location: str = Form("", description="Where the person was FOUND"),
    reporter_mobile: str = Form(""), physical_description: str = Form(""),
    reporting_center: str = Form(""),
    lat: Optional[float] = Form(None), lng: Optional[float] = Form(None),
    photo: Optional[UploadFile] = File(None),
) -> dict:
    return _intake("found", name, gender, age_band, state, district, language,
                   last_seen_location, reporter_mobile, physical_description,
                   lat, lng, reporting_center, photo)


@app.post("/reports/missing")
def report_missing(
    name: str = Form(""), gender: str = Form(""), age_band: str = Form(""),
    state: str = Form(""), district: str = Form(""), language: str = Form(""),
    last_seen_location: str = Form(""),
    reporter_mobile: str = Form(""), physical_description: str = Form(""),
    reporting_center: str = Form(""),
    lat: Optional[float] = Form(None), lng: Optional[float] = Form(None),
    photo: Optional[UploadFile] = File(None),
) -> dict:
    return _intake("missing", name, gender, age_band, state, district, language,
                   last_seen_location, reporter_mobile, physical_description,
                   lat, lng, reporting_center, photo)


# --- text search (no upload) -----------------------------------------------
class SearchQuery(BaseModel):
    type: str = "missing"                 # what you're looking for
    name: str = ""
    gender: str = ""
    age_band: str = ""
    state: str = ""
    district: str = ""
    language: str = ""
    last_seen_location: str = ""
    reporter_mobile: str = ""
    physical_description: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    scope: str = "all"
    top_k: int = 10


@app.post("/search")
def search(q: SearchQuery) -> dict:
    query = q.model_dump()
    scope, top_k = query.pop("scope"), query.pop("top_k")
    matches = ENGINE.match(query, scope=scope, top_k=top_k)
    return {"match_count": len(matches), "matches": matches}


# --- Feature 2: cross-language voice query ---------------------------------
@app.post("/voice/query")
def voice_query(
    audio: UploadFile = File(...),
    type: str = Form("missing"),
    lat: Optional[float] = Form(None), lng: Optional[float] = Form(None),
) -> dict:
    if not voice.available:
        raise HTTPException(503, "Speech backend not installed "
                                 "(pip install faster-whisper).")
    dest = config.UPLOAD_DIR / f"voice_{audio.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    trans = voice.transcribe(str(dest))
    query = voice.parse_query(trans["translated"])
    query["type"] = type
    if lat is not None and lng is not None:
        query["lat"], query["lng"] = lat, lng

    matches = ENGINE.match(query, scope="all")
    return {
        "transcription": trans,
        "parsed_query": query,
        "match_count": len(matches),
        "matches": matches,
    }


# --- inspect a stored report / re-run its match ----------------------------
@app.get("/reports/{report_id}")
def get_report(report_id: str) -> dict:
    rep = STORE.get(report_id)
    if not rep:
        raise HTTPException(404, "report not found")
    return rep.public_dict()


@app.get("/reports/{report_id}/matches")
def rerun_match(report_id: str, scope: str = "all", top_k: int = 10) -> dict:
    rep = STORE.get(report_id)
    if not rep:
        raise HTTPException(404, "report not found")
    matches = ENGINE.match(rep, scope=scope, top_k=top_k)
    return {"match_count": len(matches), "matches": matches}
