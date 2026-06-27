"""
API surface for the issue lifecycle:

  POST /api/v1/issues              raise an issue (runs Claude, returns a ticket)
  GET  /api/v1/issues              list all tickets (powers the admin dashboard)
  GET  /api/v1/issues/{id}         fetch one ticket
  POST /api/v1/issues/{id}/assign  admin assigns the ticket to a department
  GET  /api/v1/departments         department catalog (for dropdowns)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.issue import AssignRequest, IssueCreate, IssueResponse, Ticket
from app.services import database
from app.services.claude_engine import analyze_with_claude
from app.services.dedup import find_duplicate
from app.services.departments import DEPARTMENTS

router = APIRouter()

_PRIORITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escalate_priority(ticket: Ticket) -> None:
    """As duplicate reports pile up, raise the priority of the merged ticket."""
    if not ticket.ai_analysis:
        return
    current = ticket.ai_analysis.priority
    n = ticket.report_count
    target = current
    if n >= 10:
        target = "CRITICAL"
    elif n >= 3 and _PRIORITY_ORDER.index(current) < _PRIORITY_ORDER.index("HIGH"):
        target = "HIGH"
    if _PRIORITY_ORDER.index(target) > _PRIORITY_ORDER.index(current):
        ticket.ai_analysis.priority = target  # type: ignore[assignment]


@router.post("/issues", response_model=IssueResponse)
def raise_issue(payload: IssueCreate) -> IssueResponse:
    """A devotee/volunteer reports a problem. We ask Claude to classify it,
    check whether it duplicates a recent open ticket, and then either merge it
    (escalating the existing ticket) or create a new NEW ticket."""
    analysis, engine = analyze_with_claude(payload.description, payload.zone)
    department = analysis.suggested_department

    # --- Duplicate detection / auto-merge ---
    existing = find_duplicate(
        payload.description, department, payload.zone, database.list_tickets()
    )
    if existing:
        existing.report_count += 1
        existing.merged_reports.append(
            {
                "description": payload.description,
                "reporter_name": payload.reporter_name,
                "reporter_contact": payload.reporter_contact,
                "zone": payload.zone,
                "at": _now_iso(),
            }
        )
        _escalate_priority(existing)
        database.update_ticket(existing)
        return IssueResponse(
            merged=True,
            ticket=existing,
            message=(
                f"Merged into existing ticket {existing.ticket_id} "
                f"({existing.report_count} reports). Priority now "
                f"{existing.ai_analysis.priority if existing.ai_analysis else 'n/a'}."
            ),
        )

    ticket = Ticket(
        ticket_id=f"KS-{uuid.uuid4().hex[:8].upper()}",
        description=payload.description,
        reporter_name=payload.reporter_name,
        reporter_contact=payload.reporter_contact,
        zone=payload.zone,
        created_at=_now_iso(),
        status="NEW",
        ai_analysis=analysis,
        ai_engine=engine,
    )
    database.save_ticket(ticket)
    return IssueResponse(
        merged=False, ticket=ticket, message=f"Created ticket {ticket.ticket_id}."
    )


@router.get("/issues", response_model=list[Ticket])
def get_issues() -> list[Ticket]:
    """All tickets, newest first — the admin dashboard feed."""
    tickets = database.list_tickets()
    return sorted(tickets, key=lambda t: t.created_at, reverse=True)


@router.get("/issues/{ticket_id}", response_model=Ticket)
def get_issue(ticket_id: str) -> Ticket:
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@router.post("/issues/{ticket_id}/assign", response_model=Ticket)
def assign_issue(ticket_id: str, payload: AssignRequest) -> Ticket:
    """Admin assigns the ticket to a department (usually the AI suggestion)."""
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    ticket.assigned_department = payload.department
    ticket.assigned_by = payload.assigned_by
    ticket.assigned_at = _now_iso()
    ticket.status = "ASSIGNED"

    updated = database.update_ticket(ticket)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update ticket.")
    return updated


@router.get("/departments")
def get_departments() -> dict:
    """Department catalog for the admin dropdown."""
    return {
        "departments": [
            {"code": code, **meta} for code, meta in DEPARTMENTS.items()
        ]
    }
