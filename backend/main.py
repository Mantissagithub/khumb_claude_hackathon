"""Sangam API — integration app (PLAN.md §3).

Mounts the per-feature routers. Member 1's face-search router is wired here;
the other three members add one `include_router(...)` line each.

Run (from backend/):  uvicorn main:app --reload --port 8000
Docs:                 http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import os
import sys

# make `services` importable whether launched from backend/ or the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI                                   # noqa: E402
from fastapi.middleware.cors import CORSMiddleware            # noqa: E402
from fastapi.responses import RedirectResponse                # noqa: E402
from fastapi.staticfiles import StaticFiles                   # noqa: E402

from services.face_search.router import router as face_router  # noqa: E402
from sahayak.router import router as sahayak_router            # noqa: E402

app = FastAPI(title="Sahayak — Kumbh Reunification", version="0.1.0")

# Dev CORS (PLAN.md fallback; the Vite proxy is preferred in production).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/ping")
def ping() -> dict:
    return {"ok": True, "service": "sahayak", "features": ["face_search", "sahayak"]}


app.include_router(face_router)
app.include_router(sahayak_router)
# Member 2: app.include_router(voice_router)  ·  Member 3: sim  ·  Member 4: routing

# Serve the Sahayak web app (Volunteer + Admin).
_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahayak", "web")
app.mount("/app", StaticFiles(directory=_WEB, html=True), name="app")


@app.get("/")
def root():
    return RedirectResponse("/app/")
