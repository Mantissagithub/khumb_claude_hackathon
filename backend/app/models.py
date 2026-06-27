"""Internal data structures + API response shapes.

A `Report` is the unified record for BOTH a missing report (family searching)
and a found report (volunteer who found an unconscious / lost person), and
also for normalised government-registry rows. One shape => one matcher.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Report:
    id: str
    source: str = "live"          # "live" | "government"
    type: str = "missing"         # "missing" | "found"
    name: str = ""
    gender: str = ""
    age_band: str = ""
    state: str = ""
    district: str = ""
    language: str = ""
    last_seen_location: str = ""   # for FOUND reports: where the person was found
    reporting_center: str = ""
    reporter_mobile: str = ""
    physical_description: str = ""
    status: str = "Pending"
    remarks: str = ""
    # capture point (GPS of the kiosk / where photo was taken / found location)
    lat: Optional[float] = None
    lng: Optional[float] = None
    created_at: str = ""
    # biometric / appearance — never returned in API responses
    photo_path: Optional[str] = None
    face_embedding: Optional[list[float]] = field(default=None, repr=False)
    cloth_signature: Optional[dict] = None

    def public_dict(self) -> dict:
        """Serialisable view with biometrics stripped (privacy by design)."""
        d = asdict(self)
        d.pop("face_embedding", None)
        d.pop("photo_path", None)
        d["has_photo"] = self.face_embedding is not None or self.photo_path is not None
        return d
