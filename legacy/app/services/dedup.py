"""
Duplicate detection / spam control.

When 50 people report the same broken barricade in Zone 2, the Police desk
should see ONE escalating high-priority alert, not 50 tickets. Before a new
report becomes its own ticket, we check it against recent unresolved tickets:

  1. Cheap pre-filter — only tickets from the last 15 minutes, not yet resolved,
     routed to the same department (and same zone when both have one).
  2. Match — a quick Claude check (structured yes/no + which ticket), with a
     dependency-free text-similarity fallback when no API key is set.

Note: Anthropic has no native embeddings endpoint (they recommend Voyage AI),
so we use the "quick LLM check" approach rather than vector similarity.
"""

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.issue import Ticket

DUP_WINDOW_MINUTES = 15
SIMILARITY_THRESHOLD = 0.62  # for the local fallback


class DuplicateVerdict(BaseModel):
    """Structured output Claude returns when checking for duplicates."""

    is_duplicate: bool = Field(
        description="True only if the new report is about the SAME real-world "
        "incident as one of the candidates (same thing, same place)."
    )
    duplicate_of: Optional[str] = Field(
        default=None,
        description="The ticket_id of the matching candidate, or null.",
    )
    reason: str = Field(description="One short sentence explaining the verdict.")


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def candidate_tickets(
    tickets: list[Ticket], department: str, zone: str | None
) -> list[Ticket]:
    """Recent, unresolved tickets in the same department (and zone if known)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DUP_WINDOW_MINUTES)
    out: list[Ticket] = []
    for t in tickets:
        if t.status == "RESOLVED":
            continue
        if t.assigned_department and t.assigned_department != department:
            # If already routed elsewhere, it's not the same bucket.
            continue
        dept = t.assigned_department or (
            t.ai_analysis.suggested_department if t.ai_analysis else None
        )
        if dept != department:
            continue
        try:
            if _parse_iso(t.created_at) < cutoff:
                continue
        except ValueError:
            continue
        # If both have a zone, require a loose zone overlap.
        if zone and t.zone and not _zones_overlap(zone, t.zone):
            continue
        out.append(t)
    return out


def _zones_overlap(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    if a in b or b in a:
        return True
    # token overlap (e.g. "sector 2" vs "near sector 2 gate")
    return bool(set(a.split()) & set(b.split()) & {"sector", "ghat", "gate", "bridge"} or
                len(set(a.split()) & set(b.split())) >= 2)


def find_duplicate(
    new_description: str,
    department: str,
    zone: str | None,
    tickets: list[Ticket],
) -> Optional[Ticket]:
    """Return the existing ticket this report duplicates, or None."""
    candidates = candidate_tickets(tickets, department, zone)
    if not candidates:
        return None

    if settings.ANTHROPIC_API_KEY:
        match_id = _claude_duplicate_check(new_description, zone, candidates)
        if match_id:
            return next((c for c in candidates if c.ticket_id == match_id), None)
        return None

    # Fallback: local text similarity against each candidate's description/summary.
    best, best_score = None, 0.0
    for c in candidates:
        score = SequenceMatcher(None, new_description.lower(), c.description.lower()).ratio()
        if c.ai_analysis:
            score = max(
                score,
                SequenceMatcher(None, new_description.lower(),
                                c.ai_analysis.summary.lower()).ratio(),
            )
        if score > best_score:
            best, best_score = c, score
    return best if best_score >= SIMILARITY_THRESHOLD else None


def _claude_duplicate_check(
    new_description: str, zone: str | None, candidates: list[Ticket]
) -> Optional[str]:
    listing = "\n".join(
        f"- {c.ticket_id}: {c.ai_analysis.summary if c.ai_analysis else c.description}"
        f" (zone: {c.zone or 'n/a'})"
        for c in candidates
    )
    system = (
        "You are a deduplication filter for an incident control room. Decide "
        "whether a NEW report describes the same real-world incident as any of "
        "the existing open tickets (same problem, same place — not merely the "
        "same category). Be conservative: only mark a duplicate when you are "
        "confident it's the same incident."
    )
    user = (
        f"NEW report: {new_description}\n"
        f"NEW zone: {zone or 'n/a'}\n\n"
        f"Existing open tickets:\n{listing}"
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=DuplicateVerdict,
        )
        verdict = response.parsed_output
        if verdict and verdict.is_duplicate:
            return verdict.duplicate_of
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[KumbhSeva] Duplicate check failed, treating as unique: {exc}")
        return None
