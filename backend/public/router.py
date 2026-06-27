"""Public router: anonymous missing-person submission. Mounted at /api/public.

No auth — anyone can report. A submission lands in the `submissions` inbox as
'pending' for an operator to review. Light anti-abuse via a honeypot field and a
simple in-memory per-IP rate limit (best-effort, resets on restart).
"""

from __future__ import annotations

import os
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from shared import geo
from shared.db import PHOTOS_DIR, get_conn

router = APIRouter()

_ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
_RATE: dict[str, list[float]] = {}
_RATE_MAX = 10          # submissions
_RATE_WINDOW = 60.0     # per 60s per IP


def _rate_ok(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _RATE.get(ip, []) if now - t < _RATE_WINDOW]
    hits.append(now)
    _RATE[ip] = hits
    return len(hits) <= _RATE_MAX


def _save_photo(photo: UploadFile) -> str | None:
    if not photo or not photo.filename:
        return None
    ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else "jpg"
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported image type")
    fname = f"sub_{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(PHOTOS_DIR, fname)
    with open(dest, "wb") as f:
        f.write(photo.file.read())
    # Stored relative to backend/data so the frontend can resolve it later.
    return f"photos/{fname}"


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit(
    request: Request,
    reporter_phone: str = Form(...),
    missing_name: str | None = Form(None),
    gender: str | None = Form(None),
    age_band: str | None = Form(None),
    last_seen_location: str | None = Form(None),
    physical_description: str | None = Form(None),
    reporter_name: str | None = Form(None),
    hp: str | None = Form(None),  # honeypot — bots fill it, humans don't
    photo: UploadFile | None = File(None),
):
    if hp:
        # Silently accept-and-drop suspected bots.
        return {"ok": True, "submission_id": None, "message": "Received."}

    ip = request.client.host if request.client else "unknown"
    if not _rate_ok(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many submissions, slow down.")

    photo_path = _save_photo(photo)
    lat, lng, zone = geo.resolve(last_seen_location)

    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO submissions
               (missing_name, gender, age_band, last_seen_location, physical_description,
                photo_path, reporter_name, reporter_phone, lat, lng, zone, source_ip)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (missing_name, gender, age_band, last_seen_location, physical_description,
             photo_path, reporter_name, reporter_phone, lat, lng, zone, ip),
        )
        conn.commit()
        sub_id = cur.lastrowid
    finally:
        conn.close()

    return {
        "ok": True,
        "submission_id": sub_id,
        "message": "Report received. Our team will review and contact you on a match.",
    }
