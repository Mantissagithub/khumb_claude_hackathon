"""In-memory registry of live reports + the loaded government registry.

A real deployment swaps this for SQLite-at-the-node + Postgres-at-centre with
an append-only sync log (see PLAN.md / README). The matching API is identical;
only persistence changes — so the engine never touches storage internals.
"""
from __future__ import annotations

import itertools
from typing import Optional

from .models import Report


class Store:
    def __init__(self, government_rows: list[dict]):
        self._live: dict[str, Report] = {}
        self._counter = itertools.count(1)
        # government rows kept as plain dicts (text-only, no biometrics)
        self.government: list[dict] = government_rows

    def new_id(self, kind: str) -> str:
        return f"{kind.upper()}-LIVE-{next(self._counter):05d}"

    def add(self, report: Report) -> Report:
        self._live[report.id] = report
        return report

    def get(self, report_id: str) -> Optional[Report]:
        return self._live.get(report_id)

    def all_live(self) -> list[Report]:
        return list(self._live.values())

    def live_of_type(self, type_: str) -> list[Report]:
        return [r for r in self._live.values() if r.type == type_]

    def stats(self) -> dict:
        live = self.all_live()
        return {
            "government_records": len(self.government),
            "live_reports": len(live),
            "live_missing": sum(1 for r in live if r.type == "missing"),
            "live_found": sum(1 for r in live if r.type == "found"),
        }
