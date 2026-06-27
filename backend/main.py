"""Sangam / Sahayak — unified FastAPI integration app.

Combines the work from all branches into one runnable API:

  ashutosh  — auth + public submission + admin review (needs the SQLite DB)
  manan     — face_search verdicts + the Sahayak role-based web app

Every feature router is mounted defensively: if an optional dependency for one
feature is missing (e.g. the heavy face stack), that feature is skipped with a
warning and the rest of the API still boots. Check what loaded at GET /api/ping.

Run (from backend/):  uvicorn main:app --reload --port 8000
Docs:                 http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

# Make both `admin`/`auth`/... (top level) and `services`/`sahayak` importable
# whether launched from backend/ or the repo root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI                                   # noqa: E402
from fastapi.middleware.cors import CORSMiddleware            # noqa: E402
from fastapi.responses import RedirectResponse                # noqa: E402
from fastapi.staticfiles import StaticFiles                   # noqa: E402

log = logging.getLogger("sangam")

# Track which feature groups loaded so /api/ping can report capabilities.
_LOADED: list[str] = []
_SKIPPED: dict[str, str] = {}


def _try(name: str, fn) -> None:
    """Run a router-mount step, recording success/failure without crashing boot."""
    try:
        fn()
        _LOADED.append(name)
    except Exception as exc:  # noqa: BLE001 — defensive integration boundary
        _SKIPPED[name] = f"{type(exc).__name__}: {exc}"
        log.warning("feature %r not mounted: %s", name, exc)


# --- ashutosh: auth + public + admin (SQLite-backed) -----------------------
try:
    from shared.db import PHOTOS_DIR, init_db  # noqa: E402

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            init_db()
        except Exception as exc:  # noqa: BLE001
            log.warning("init_db failed: %s", exc)
        yield

except Exception as exc:  # noqa: BLE001
    PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "data", "photos")
    _SKIPPED["db"] = f"{type(exc).__name__}: {exc}"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield


app = FastAPI(title="Sangam / Sahayak API", version="1.0", lifespan=lifespan)

# Dev CORS (the Vite proxy is preferred in production).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/ping")
def ping() -> dict:
    return {"ok": True, "service": "sangam-sahayak", "loaded": _LOADED, "skipped": _SKIPPED}


def _mount_auth() -> None:
    from auth.router import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])


def _mount_public() -> None:
    from public.router import router as public_router
    app.include_router(public_router, prefix="/api/public", tags=["public"])


def _mount_admin() -> None:
    from admin.router import router as admin_router
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


def _mount_face_search() -> None:
    from services.face_search.router import router as face_router
    app.include_router(face_router)


def _mount_sahayak() -> None:
    from sahayak.router import router as sahayak_router
    app.include_router(sahayak_router)


_try("auth", _mount_auth)
_try("public", _mount_public)
_try("admin", _mount_admin)
_try("face_search", _mount_face_search)
_try("sahayak", _mount_sahayak)

# Serve uploaded submission photos at /api/media/photos/<file>.
try:
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    app.mount("/api/media/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")
except Exception as exc:  # noqa: BLE001
    log.warning("photo mount skipped: %s", exc)

# Serve the Sahayak web app (Volunteer + Admin) at /app.
_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahayak", "web")
if os.path.isdir(_WEB):
    app.mount("/app", StaticFiles(directory=_WEB, html=True), name="app")

    @app.get("/")
    def root():
        return RedirectResponse("/app/")
