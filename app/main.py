"""
KumbhSeva HTTP API entrypoint.

    uvicorn app.main:app --reload

Exposes the full control-room pipeline (AI triage, ticket store, knowledge-graph
asset linking, assignment + dispatch roadmap) as a JSON API under /api/v1, ready
for the frontend template to consume. CORS is wide-open by default for local dev;
lock it down with KUMBHSEVA_CORS_ORIGINS (comma-separated) in production.

Interactive docs: /docs
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import schemas
from app.api.deps import get_settings, get_store_bundle
from app.api.routes import router

app = FastAPI(
    title="KumbhSeva API",
    version="1.0.0",
    description="AI issue routing for the Kumbh Mela control room.",
)

_origins = os.getenv("KUMBHSEVA_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _origins.strip() == "*" else
    [o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", response_model=schemas.Health, tags=["meta"],
         summary="Status + which AI engine / storage backend is live")
def health():
    cfg = get_settings()
    _, mode, err = get_store_bundle()
    return {
        "status": "ok",
        "ai_engine": "claude" if cfg["claude_key"] else "keyword fallback",
        "storage": "supabase" if mode == "supabase" else f"local{f' ({err})' if err else ''}",
        "model": cfg["claude_model"],
        "stages": schemas.STAGES,
    }


@app.get("/", tags=["meta"], summary="Service banner")
def root():
    return {"service": "KumbhSeva API", "docs": "/docs", "health": "/health",
            "api": "/api/v1"}
