"""Sahayak REST + WebSocket API.

Cases (register/list/photo), match candidates (list/confirm/reject), live
stats, preset centers, and a /ws realtime channel. Reuses the face engine
from face_search for embeddings.
"""
from __future__ import annotations

import os
import shutil
import uuid

from fastapi import (APIRouter, File, Form, HTTPException, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from services.face_search.logic import FaceSearchService
from .hub import Hub
from .store import Store

router = APIRouter(tags=["sahayak"])

STORE = Store()
HUB = Hub()
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Preset lost-and-found centers (approx Nashik/Trimbak coords) for the map.
CENTERS = [
    {"id": "trimbak", "name": "Trimbakeshwar Kendra", "lat": 19.9322, "lng": 73.5300},
    {"id": "ramkund", "name": "Ramkund Ghat Center", "lat": 19.9990, "lng": 73.7896},
    {"id": "panchavati", "name": "Panchavati Control Room", "lat": 20.0070, "lng": 73.7910},
    {"id": "adgaon", "name": "Adgaon Center", "lat": 20.0155, "lng": 73.8269},
    {"id": "takli", "name": "Takli Sangam Center", "lat": 19.9600, "lng": 73.7700},
]
_CENTER_BY_ID = {c["id"]: c for c in CENTERS}


def _embedder():
    return FaceSearchService.get().pipe.embedder


def _targets_for(case: dict) -> set[str]:
    return {"admin", f"center:{case.get('center', '')}"}


@router.get("/api/centers")
def centers():
    return CENTERS


@router.get("/api/stats")
def stats():
    return {**STORE.stats(), "live_connections": HUB.count}


@router.get("/api/cases")
def list_cases(type: str = None, status: str = None, center: str = None):
    return STORE.list_cases(type, status, center)


@router.get("/api/cases/{case_id}/photo")
def case_photo(case_id: str):
    c = STORE.cases.get(case_id)
    if not c or not c.get("photo_path") or not os.path.isfile(c["photo_path"]):
        raise HTTPException(404, "no photo")
    return FileResponse(c["photo_path"])


@router.get("/api/candidates")
def candidates():
    return STORE.pending_candidates()


@router.post("/api/cases/register")
async def register(
    type: str = Form(..., description="missing | found"),
    name: str = Form(""), gender: str = Form(""), age_band: str = Form(""),
    center: str = Form(...), location: str = Form(""),
    reporter_mobile: str = Form(""), description: str = Form(""),
    photo: UploadFile = File(None),
):
    if type not in ("missing", "found"):
        raise HTTPException(400, "type must be 'missing' or 'found'")
    photo_path, embedding = None, None
    if photo is not None:
        ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
        photo_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
        with open(photo_path, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        emb = await run_in_threadpool(_embedder().embed_image, photo_path)
        embedding = emb if emb is not None else None

    fields = {"name": name, "gender": gender, "age_band": age_band,
              "center": center, "location": location,
              "reporter_mobile": reporter_mobile, "description": description}
    case = STORE.register(type, fields, photo_path, embedding)
    await HUB.broadcast(_targets_for(case), "case.created", STORE.public(case))

    new_cands = STORE.auto_match(case)
    for cand in new_cands:
        targets = {"admin"}
        for side in ("missing", "found"):
            if cand.get(side):
                targets.add(f"center:{cand[side].get('center', '')}")
        await HUB.broadcast(targets, "match.candidate", cand)

    return {"case": STORE.public(case), "candidates": new_cands,
            "face_detected": embedding is not None}


@router.post("/api/candidates/{mid}/{action}")
async def resolve(mid: str, action: str):
    if action not in ("confirm", "reject"):
        raise HTTPException(400, "action must be 'confirm' or 'reject'")
    view = STORE.resolve(mid, confirm=(action == "confirm"))
    if not view:
        raise HTTPException(404, "candidate not found or already resolved")
    targets = {"admin"}
    for side in ("missing", "found"):
        if view.get(side):
            targets.add(f"center:{view[side].get('center', '')}")
    await HUB.broadcast(targets, "match.resolved", view)
    if action == "confirm":
        for side in ("missing", "found"):
            if view.get(side):
                await HUB.broadcast(targets, "status.changed",
                                    {"case_id": view[side]["id"], "status": "reunited"})
    return view


@router.websocket("/ws")
async def ws(ws: WebSocket):
    role = ws.query_params.get("role")
    center = ws.query_params.get("center")
    rooms: set[str] = set()
    if role == "admin":
        rooms.add("admin")
    if center:
        rooms.add(f"center:{center}")
    if not rooms:
        rooms.add("admin")
    await HUB.connect(ws, rooms)
    try:
        await ws.send_json({"event": "connected", "data": {"rooms": sorted(rooms)}})
        while True:
            await ws.receive_text()   # client heartbeats; ignored
    except WebSocketDisconnect:
        HUB.disconnect(ws)
    except Exception:
        HUB.disconnect(ws)
