"""Admin/staff router: review queue, matching, decisions, staff & analytics.

Mounted at /api/admin. All routes require a valid staff token; staff-management
and analytics additionally require the 'admin' role.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from shared.db import get_conn
from shared.security import get_current_user, hash_password, require_role

router = APIRouter()

_STOP = {"in", "a", "the", "with", "has", "near", "of", "and", "man", "woman", "wearing"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tokens(*parts: str | None) -> set[str]:
    text = " ".join(p for p in parts if p).lower()
    return {w for w in re.findall(r"[a-z0-9]+", text) if w not in _STOP and len(w) > 2}


def _row_to_submission(r) -> dict:
    return dict(r)


# ─────────────────────────── Submissions queue ───────────────────────────

@router.get("/submissions")
def list_submissions(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    clauses, params = [], []
    if status_filter:
        clauses.append("review_status = ?")
        params.append(status_filter)
    if q:
        clauses.append("(missing_name LIKE ? OR physical_description LIKE ? OR last_seen_location LIKE ?)")
        params += [f"%{q}%"] * 3
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = get_conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM submissions {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM submissions {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    finally:
        conn.close()
    return {"items": [_row_to_submission(r) for r in rows], "total": total}


@router.get("/submissions/{sub_id}")
def get_submission(sub_id: int, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return _row_to_submission(row)


class MatchBody(BaseModel):
    top_n: int = 5


@router.post("/submissions/{sub_id}/match")
def run_match(sub_id: int, body: MatchBody = MatchBody(), user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        if not sub:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")

        sub_tokens = _tokens(sub["missing_name"], sub["physical_description"], sub["last_seen_location"])
        # Candidate pool: still-active missing cases.
        cases = conn.execute(
            "SELECT case_id, name, gender, age_band, zone, last_seen_location, "
            "physical_description, status FROM cases WHERE status = 'Active'"
        ).fetchall()

        scored = []
        for c in cases:
            case_tokens = _tokens(c["name"], c["physical_description"], c["last_seen_location"])
            overlap = len(sub_tokens & case_tokens)
            denom = len(sub_tokens | case_tokens) or 1
            text_score = overlap / denom
            # Lightweight attribute boosts.
            if sub["gender"] and c["gender"] and sub["gender"] == c["gender"]:
                text_score += 0.15
            if sub["age_band"] and c["age_band"] and sub["age_band"] == c["age_band"]:
                text_score += 0.15
            if sub["zone"] and c["zone"] and sub["zone"] == c["zone"]:
                text_score += 0.20
            if text_score <= 0:
                continue
            reasons = []
            if overlap:
                reasons.append(f"{overlap} shared description terms")
            if sub["gender"] and sub["gender"] == c["gender"]:
                reasons.append("same gender")
            if sub["age_band"] and sub["age_band"] == c["age_band"]:
                reasons.append("same age band")
            if sub["zone"] and sub["zone"] == c["zone"]:
                reasons.append("same zone")
            scored.append({
                "case_id": c["case_id"],
                "name": c["name"],
                "gender": c["gender"],
                "age_band": c["age_band"],
                "zone": c["zone"],
                "last_seen_location": c["last_seen_location"],
                "physical_description": c["physical_description"],
                "score": round(min(text_score, 1.0), 3),
                "reason": ", ".join(reasons) or "weak text overlap",
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        candidates = scored[: body.top_n]

        if sub["review_status"] == "pending":
            conn.execute(
                "UPDATE submissions SET review_status = 'reviewing', reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                (user["id"], _now(), sub_id),
            )
            conn.commit()
    finally:
        conn.close()
    return {"submission_id": sub_id, "candidates": candidates}


class DecisionBody(BaseModel):
    case_id: str | None = None
    note: str | None = None


@router.post("/submissions/{sub_id}/confirm")
def confirm_match(sub_id: int, body: DecisionBody, user: dict = Depends(get_current_user)):
    if not body.case_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "case_id is required to confirm")
    conn = get_conn()
    try:
        sub = conn.execute("SELECT id FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        if not sub:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
        case = conn.execute("SELECT case_id FROM cases WHERE case_id = ?", (body.case_id,)).fetchone()
        if not case:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
        conn.execute(
            "UPDATE submissions SET review_status='matched', matched_case_id=?, reviewed_by=?, "
            "reviewed_at=?, decision_note=? WHERE id=?",
            (body.case_id, user["id"], _now(), body.note, sub_id),
        )
        conn.execute("UPDATE cases SET status='Matched' WHERE case_id=?", (body.case_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "submission_id": sub_id, "matched_case_id": body.case_id, "review_status": "matched"}


@router.post("/submissions/{sub_id}/promote")
def promote(sub_id: int, body: DecisionBody, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        sub = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        if not sub:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
        new_id = f"PUB-{sub_id:05d}"
        name = sub["missing_name"]
        conn.execute(
            """INSERT OR REPLACE INTO cases
               (case_id, type, name, name_normalized, gender, age_band, last_seen_location,
                lat, lng, zone, reporter_mobile, physical_description, photo_path,
                status, reported_at, remarks)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (new_id, "missing", name, (name or "").lower().strip(), sub["gender"], sub["age_band"],
             sub["last_seen_location"], sub["lat"], sub["lng"], sub["zone"], sub["reporter_phone"],
             sub["physical_description"], sub["photo_path"], "Active", _now(),
             f"Promoted from public submission #{sub_id}"),
        )
        conn.execute(
            "UPDATE submissions SET review_status='promoted', created_case_id=?, reviewed_by=?, "
            "reviewed_at=?, decision_note=? WHERE id=?",
            (new_id, user["id"], _now(), body.note, sub_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "submission_id": sub_id, "created_case_id": new_id, "review_status": "promoted"}


@router.post("/submissions/{sub_id}/reject")
def reject(sub_id: int, body: DecisionBody, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        res = conn.execute(
            "UPDATE submissions SET review_status='rejected', reviewed_by=?, reviewed_at=?, "
            "decision_note=? WHERE id=?",
            (user["id"], _now(), body.note, sub_id),
        )
        conn.commit()
    finally:
        conn.close()
    if res.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return {"ok": True, "submission_id": sub_id, "review_status": "rejected"}


# ─────────────────────────── Cases ───────────────────────────

@router.get("/cases")
def list_cases(
    q: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    zone: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    clauses, params = [], []
    if q:
        clauses.append("(name LIKE ? OR physical_description LIKE ? OR case_id LIKE ?)")
        params += [f"%{q}%"] * 3
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)
    if zone:
        clauses.append("zone = ?")
        params.append(zone)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = get_conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM cases {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM cases {where} ORDER BY reported_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    finally:
        conn.close()
    return {"items": [dict(r) for r in rows], "total": total}


@router.post("/cases/{case_id}/reunite")
def reunite(case_id: str, body: DecisionBody, user: dict = Depends(get_current_user)):
    conn = get_conn()
    try:
        res = conn.execute("UPDATE cases SET status='Reunited' WHERE case_id=?", (case_id,))
        conn.commit()
    finally:
        conn.close()
    if res.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return {"ok": True, "case_id": case_id, "status": "Reunited"}


# ─────────────────────────── Staff (admin only) ───────────────────────────

class StaffCreate(BaseModel):
    username: str
    password: str
    role: str  # operator | admin
    name: str


@router.get("/staff")
def list_staff(user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, username, role, name, created_at FROM staff ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def create_staff(body: StaffCreate, user: dict = Depends(require_role("admin"))):
    if body.role not in ("operator", "admin"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be operator or admin")
    conn = get_conn()
    try:
        try:
            cur = conn.execute(
                "INSERT INTO staff (username, password_hash, role, name) VALUES (?,?,?,?)",
                (body.username, hash_password(body.password), body.role, body.name),
            )
            conn.commit()
        except Exception:
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
        new_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": new_id, "username": body.username, "role": body.role, "name": body.name}


@router.delete("/staff/{staff_id}")
def delete_staff(staff_id: int, user: dict = Depends(require_role("admin"))):
    if staff_id == user["id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account")
    conn = get_conn()
    try:
        res = conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))
        conn.commit()
    finally:
        conn.close()
    if res.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff not found")
    return {"ok": True}


# ─────────────────────────── Analytics (admin only) ───────────────────────────

@router.get("/analytics/summary")
def analytics(user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    try:
        cases_total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute("SELECT status, COUNT(*) n FROM cases GROUP BY status").fetchall()
        }
        subs = {
            r["review_status"]: r["n"]
            for r in conn.execute(
                "SELECT review_status, COUNT(*) n FROM submissions GROUP BY review_status"
            ).fetchall()
        }
        subs_total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        top_zones = [
            dict(r)
            for r in conn.execute(
                "SELECT zone, COUNT(*) n FROM cases WHERE zone IS NOT NULL "
                "GROUP BY zone ORDER BY n DESC LIMIT 5"
            ).fetchall()
        ]
    finally:
        conn.close()
    return {
        "cases_total": cases_total,
        "cases_by_status": by_status,
        "submissions_total": subs_total,
        "submissions_by_status": subs,
        "top_zones": top_zones,
    }
