"""
A tiny JSON-file 'database' that simulates a NoSQL ticket store for the
prototype. Swap this module for Firestore/Postgres later without touching the
API layer — the function signatures are what the rest of the app depends on.
"""

import json
import os
from threading import Lock

from app.core.config import settings
from app.models.issue import Ticket

_lock = Lock()


def _ensure_db() -> None:
    os.makedirs(os.path.dirname(settings.DB_FILE) or ".", exist_ok=True)
    if not os.path.exists(settings.DB_FILE):
        with open(settings.DB_FILE, "w") as f:
            json.dump([], f)


def _read_all() -> list[dict]:
    _ensure_db()
    with open(settings.DB_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _write_all(records: list[dict]) -> None:
    with open(settings.DB_FILE, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def save_ticket(ticket: Ticket) -> Ticket:
    with _lock:
        records = _read_all()
        records.append(ticket.model_dump())
        _write_all(records)
    return ticket


def list_tickets() -> list[Ticket]:
    return [Ticket(**r) for r in _read_all()]


def get_ticket(ticket_id: str) -> Ticket | None:
    for r in _read_all():
        if r.get("ticket_id") == ticket_id:
            return Ticket(**r)
    return None


def update_ticket(ticket: Ticket) -> Ticket | None:
    with _lock:
        records = _read_all()
        for i, r in enumerate(records):
            if r.get("ticket_id") == ticket.ticket_id:
                records[i] = ticket.model_dump()
                _write_all(records)
                return ticket
    return None
