"""
KumbhSeva HTTP API — every piece of the control-room logic, exposed for the
frontend.

This wraps the SAME services the Streamlit admin uses:
  - app.services.triage          → AI routing (Claude + keyword fallback)
  - app.services.store           → ticket persistence (Local JSON / Supabase)
  - app.services.knowledge_graph → nearest responder centre / on-ground assets

Tickets are plain dicts whose keys match the Supabase `tickets` columns, so a
record created here drops cleanly into either backend.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas
from app.api.deps import get_settings, get_store, get_store_bundle
from app.services import triage
from app.services.knowledge_graph import (
    ASSETS,
    nearest_asset_detail,
    nearby_assets,
)
from app.services.triage import RESPONDERS

router = APIRouter()

_RESPONDER_CODES = ("POLICE", "MEDICAL", "FIRE_BRIGADE")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find(store, ticket_id: str) -> dict:
    ticket = next(
        (t for t in store.list_tickets() if t.get("ticket_id") == ticket_id), None
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


def _needs_enrichment(t: dict) -> bool:
    return not t.get("department") or not t.get("summary")


def _enrich(store, tickets: list[dict], cfg: dict) -> list[dict]:
    """Run triage on any ticket that arrived without an AI suggestion (e.g. raw
    citizen uploads written straight to Supabase), and persist it once."""
    out = []
    for t in tickets:
        if _needs_enrichment(t):
            analysis, engine = triage.classify(
                description=t.get("description", ""),
                api_key=cfg["claude_key"],
                model=cfg["claude_model"],
                zone=t.get("zone"),
                lat=t.get("latitude"),
                lon=t.get("longitude"),
            )
            patch = {**analysis, "ai_engine": engine}
            if not t.get("status"):
                patch["status"] = "NEW"
            if t.get("dispatch_stage") is None:
                patch["dispatch_stage"] = 0
            try:
                store.update_ticket(t["ticket_id"], patch)
            except Exception as exc:  # noqa: BLE001
                print(f"[KumbhSeva] enrichment write-back failed for "
                      f"{t.get('ticket_id')}: {exc}")
            t = {**t, **patch}
        out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Issues
# --------------------------------------------------------------------------- #
@router.post("/issues", response_model=schemas.Ticket, status_code=201,
             summary="Raise an issue (runs AI triage, then stores the ticket)")
def create_issue(payload: schemas.IssueCreate, store=Depends(get_store)):
    cfg = get_settings()
    analysis, engine = triage.classify(
        description=payload.description,
        api_key=cfg["claude_key"],
        model=cfg["claude_model"],
        zone=payload.zone,
        lat=payload.latitude,
        lon=payload.longitude,
    )
    ticket = {
        "ticket_id": f"KS-{uuid.uuid4().hex[:8].upper()}",
        "description": payload.description.strip(),
        "zone": payload.zone or None,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "photo_b64": payload.photo_b64,
        "photo_url": payload.photo_url,
        "reporter_name": payload.reporter_name or None,
        "reporter_contact": payload.reporter_contact or None,
        "status": "NEW",
        "dispatch_stage": 0,
        "created_at": _now(),
        "ai_engine": engine,
        **analysis,
    }
    store.add_ticket(ticket)
    return ticket


@router.get("/issues", response_model=list[schemas.Ticket],
            summary="List tickets (dashboard feed, newest first)")
def list_issues(
    status: str | None = Query(default=None, description="Filter by status, e.g. NEW."),
    department: str | None = Query(default=None, description="Filter by suggested department."),
    store=Depends(get_store),
):
    tickets = _enrich(store, store.list_tickets(), get_settings())
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    if department:
        tickets = [t for t in tickets if t.get("department") == department]
    return tickets


@router.get("/issues/{ticket_id}", response_model=schemas.Ticket,
            summary="Fetch one ticket")
def get_issue(ticket_id: str, store=Depends(get_store)):
    return _find(store, ticket_id)


@router.post("/issues/{ticket_id}/assign", response_model=schemas.Ticket,
             summary="Admin assigns the ticket to a responder")
def assign_issue(ticket_id: str, payload: schemas.AssignRequest,
                 store=Depends(get_store)):
    _find(store, ticket_id)  # 404 if missing
    store.update_ticket(ticket_id, {
        "assigned_department": payload.department,
        "status": "ASSIGNED",
        "assigned_at": _now(),
        "dispatch_stage": 1,
    })
    return _find(store, ticket_id)


@router.post("/issues/{ticket_id}/dispatch", response_model=schemas.Ticket,
             summary="Advance the dispatch roadmap (Reported→…→Resolved)")
def dispatch_issue(ticket_id: str, payload: schemas.DispatchRequest,
                   store=Depends(get_store)):
    ticket = _find(store, ticket_id)
    if not ticket.get("assigned_department"):
        raise HTTPException(status_code=409,
                            detail="Assign a responder before dispatching.")
    patch = {"dispatch_stage": payload.stage}
    patch["status"] = "RESOLVED" if payload.stage >= len(schemas.STAGES) - 1 else "ASSIGNED"
    store.update_ticket(ticket_id, patch)
    return _find(store, ticket_id)


@router.get("/issues/{ticket_id}/responder-centres",
            response_model=list[schemas.ResponderCentre],
            summary="Nearest centre for each of the three responders")
def responder_centres(ticket_id: str, store=Depends(get_store)):
    t = _find(store, ticket_id)
    return _centres_for(t.get("department"), t.get("latitude"),
                        t.get("longitude"), t.get("zone"))


# --------------------------------------------------------------------------- #
# Triage preview (no persistence)
# --------------------------------------------------------------------------- #
@router.post("/triage", response_model=schemas.TriageResponse,
             summary="Run AI triage on a description without saving a ticket")
def triage_preview(payload: schemas.TriageRequest):
    cfg = get_settings()
    analysis, engine = triage.classify(
        description=payload.description,
        api_key=cfg["claude_key"],
        model=cfg["claude_model"],
        zone=payload.zone,
        lat=payload.latitude,
        lon=payload.longitude,
    )
    return {**analysis, "ai_engine": engine}


# --------------------------------------------------------------------------- #
# Catalogs — departments & knowledge-graph assets
# --------------------------------------------------------------------------- #
@router.get("/departments", response_model=list[schemas.Department],
            summary="Responder catalog")
def departments():
    return [{"code": code, **meta} for code, meta in RESPONDERS.items()]


@router.get("/assets", summary="On-ground assets (knowledge graph)")
def assets(zone: str | None = Query(default=None,
                                    description="Filter to assets near a zone string.")):
    return nearby_assets(zone) if zone else ASSETS


@router.get("/assets/nearest", response_model=schemas.ResponderCentre,
            summary="Nearest responder centre for a department + location")
def nearest(
    department: schemas.ResponderDept,
    latitude: float | None = None,
    longitude: float | None = None,
    zone: str | None = None,
):
    detail = nearest_asset_detail(department, latitude, longitude, zone)
    if not detail:
        raise HTTPException(status_code=404, detail="No mapped centre for that department.")
    return {"department": department, "suggested": False, **detail}


def _centres_for(suggested_dept, lat, lon, zone) -> list[dict]:
    out = []
    for code in _RESPONDER_CODES:
        detail = nearest_asset_detail(code, lat, lon, zone) or {}
        out.append({
            "department": code,
            "suggested": code == suggested_dept,
            "code": detail.get("code"),
            "name": detail.get("name"),
            "type": detail.get("type"),
            "zone": detail.get("zone"),
            "distance_km": detail.get("distance_km"),
        })
    return out
