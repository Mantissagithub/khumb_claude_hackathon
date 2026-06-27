"""In-memory case store + cross-center face matching.

A 'case' is a missing report or a found person. When a case is registered we
auto-search the opposite type for face matches and raise match *candidates*
for an admin to confirm (human-in-the-loop). In-memory keeps the demo simple;
swap for SQLite without touching the API (see PLAN.md).
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Optional

import numpy as np

STRONG, LIKELY, WEAK = 0.62, 0.45, 0.32


def confidence_pct(score: float) -> float:
    return round(max(0.0, min(1.0, (score - 0.2) / 0.6)) * 100, 1)


def band(score: float) -> tuple[str, str]:
    if score >= STRONG:
        return "STRONG", "Very likely the same person"
    if score >= LIKELY:
        return "LIKELY", "Likely the same person"
    if score >= WEAK:
        return "POSSIBLE", "Possible — needs review"
    return "NO_MATCH", "No match"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, threshold: float = LIKELY, surface_from: float = WEAK):
        self.cases: dict[str, dict] = {}
        self.candidates: dict[str, dict] = {}
        self.thr = threshold              # auto-alert threshold
        self.surface = surface_from       # show in review queue from here
        self._emb: dict[str, np.ndarray] = {}   # case_id -> embedding (not serialized)
        self._cid = itertools.count(1)
        self._mid = itertools.count(1)

    # -- cases --------------------------------------------------------------
    def register(self, type_: str, fields: dict,
                 photo_path: Optional[str], embedding) -> dict:
        cid = f"{'M' if type_ == 'missing' else 'F'}-{next(self._cid):04d}"
        case = {"id": cid, "type": type_, "status": "open",
                "created_at": _now(), "has_face": embedding is not None,
                "has_photo": photo_path is not None, "photo_path": photo_path}
        case.update(fields)
        self.cases[cid] = case
        if embedding is not None:
            self._emb[cid] = np.asarray(embedding, dtype="float32")
        return case

    def public(self, case: dict) -> dict:
        return {k: v for k, v in case.items() if k != "photo_path"}

    def list_cases(self, type_: Optional[str] = None, status: Optional[str] = None,
                   center: Optional[str] = None) -> list[dict]:
        out = []
        for c in self.cases.values():
            if type_ and c["type"] != type_:
                continue
            if status and c["status"] != status:
                continue
            if center and c.get("center") != center:
                continue
            out.append(self.public(c))
        return sorted(out, key=lambda x: x["created_at"], reverse=True)

    # -- matching -----------------------------------------------------------
    def auto_match(self, case: dict, top: int = 3) -> list[dict]:
        """Search the opposite-type open cases; raise candidates >= surface."""
        cid = case["id"]
        if cid not in self._emb:
            return []
        opp = "missing" if case["type"] == "found" else "found"
        q = self._emb[cid]
        scored = []
        for other in self.cases.values():
            if other["type"] != opp or other["status"] != "open":
                continue
            oid = other["id"]
            if oid not in self._emb:
                continue
            score = float(np.dot(q, self._emb[oid]))
            if score >= self.surface:
                scored.append((score, other))
        scored.sort(key=lambda s: s[0], reverse=True)

        created = []
        for score, other in scored[:top]:
            missing = case if case["type"] == "missing" else other
            found = other if case["type"] == "missing" else case
            mid = f"MATCH-{next(self._mid):04d}"
            bnd, label = band(score)
            cand = {"id": mid, "missing_id": missing["id"], "found_id": found["id"],
                    "score": round(score, 4), "confidence_pct": confidence_pct(score),
                    "band": bnd, "verdict": label,
                    "is_match": score >= self.thr, "status": "pending",
                    "created_at": _now()}
            self.candidates[mid] = cand
            created.append(self._candidate_view(cand))
        return created

    def _candidate_view(self, cand: dict) -> dict:
        m = self.cases.get(cand["missing_id"], {})
        f = self.cases.get(cand["found_id"], {})
        return {**cand,
                "missing": self.public(m) if m else None,
                "found": self.public(f) if f else None}

    def pending_candidates(self) -> list[dict]:
        return [self._candidate_view(c) for c in self.candidates.values()
                if c["status"] == "pending"]

    def resolve(self, mid: str, confirm: bool) -> Optional[dict]:
        cand = self.candidates.get(mid)
        if not cand or cand["status"] != "pending":
            return None
        cand["status"] = "confirmed" if confirm else "rejected"
        cand["resolved_at"] = _now()
        if confirm:
            for key in ("missing_id", "found_id"):
                c = self.cases.get(cand[key])
                if c:
                    c["status"] = "reunited"
            # drop other pending candidates referencing these two cases
            for other in self.candidates.values():
                if other["status"] == "pending" and (
                        other["missing_id"] == cand["missing_id"]
                        or other["found_id"] == cand["found_id"]):
                    other["status"] = "superseded"
        return self._candidate_view(cand)

    def stats(self) -> dict:
        cs = list(self.cases.values())
        return {"total": len(cs),
                "missing": sum(1 for c in cs if c["type"] == "missing"),
                "found": sum(1 for c in cs if c["type"] == "found"),
                "reunited": sum(1 for c in cs if c["status"] == "reunited"),
                "open": sum(1 for c in cs if c["status"] == "open"),
                "pending_matches": sum(1 for c in self.candidates.values()
                                       if c["status"] == "pending")}
