"""FROZEN canonical Case model (PLAN.md §4.1).

Do NOT change after the contract freeze — every service builds against this.
New request/response models belong in their owning router file, not here.
"""

from __future__ import annotations

from pydantic import BaseModel


class Case(BaseModel):
    case_id: str                      # "KMP-2027-00001" or "FOUND-0001"
    type: str = "missing"             # "missing" | "found"
    name: str | None = None           # may be empty (~15% of data)
    name_normalized: str = ""         # lowercased + trimmed for matching
    gender: str | None = None
    age_band: str | None = None       # "0-12","13-25","26-40","41-60","61-70","71-80","80+"
    language: str | None = None
    state: str | None = None
    district: str | None = None
    last_seen_location: str | None = None
    lat: float | None = None
    lng: float | None = None
    zone: str | None = None
    reporting_center: str | None = None
    reporter_mobile: str | None = None
    physical_description: str | None = None
    photo_path: str | None = None     # under data/photos/
    audio_path: str | None = None     # under data/audio/
    transcript: str | None = None
    transcript_en: str | None = None
    face_embedding: list[float] | None = None
    status: str = "Active"            # "Active" | "Reunited" | "Matched"
    reported_at: str = ""
    remarks: str | None = None
