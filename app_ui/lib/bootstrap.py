"""One-time process setup for the Streamlit app.

Puts the repo root on sys.path so the sim/planning packages (`shared`, `sim`,
`planning`) import cleanly, and makes sure the SQLite registry exists + is
seeded. Safe to call on every Streamlit rerun — the work is guarded.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_DONE = False


def init() -> None:
    global _DONE
    if _DONE:
        return
    root = str(REPO_ROOT)
    if root not in sys.path:
        # Front of the path so repo-root `shared` (sim/planning contracts) wins
        # over backend/shared — we never put backend/ on the path.
        sys.path.insert(0, root)

    from . import data
    data.ensure_db()
    _DONE = True
