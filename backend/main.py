"""Sangam FastAPI app — auth + public submission + admin review layer.

The integration lead owns this file: it runs DB seeding on startup and mounts
the routers. The 4 feature routers (face/voice/sim/routing) are added here too
once their owners build them (gated with Depends(get_current_user)).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from admin.router import router as admin_router
from auth.router import router as auth_router
from public.router import router as public_router
from shared.db import PHOTOS_DIR, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sangam API", version="1.0", lifespan=lifespan)

# Vite proxies /api in dev so CORS isn't strictly needed, but enable it for
# direct access (e.g. the /docs Authorize button from another origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/ping")
def ping():
    return {"ok": True, "service": "sangam"}


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(public_router, prefix="/api/public", tags=["public"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

# Serve uploaded submission photos at /api/media/photos/<file>.
os.makedirs(PHOTOS_DIR, exist_ok=True)
app.mount("/api/media/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")
