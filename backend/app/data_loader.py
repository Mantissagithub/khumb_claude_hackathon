"""Load and normalise the five provided CSVs into in-memory structures.

Outputs:
  * the government registry (2,500 synthetic missing-person rows), normalised
  * geo layers: zones, CCTV, police stations, chokepoints/parking
  * a GeoContext object that answers "for this point: which zone, nearest
    police station, how many cameras nearby" and resolves a free-text
    last-seen location to coordinates via a small gazetteer.

Pure standard-library (csv) so it runs with zero extra dependencies.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from . import config, geo


def _clean(s: Optional[str]) -> str:
    return (s or "").strip()


# Generic place words carry no location identity; drop them before comparing
# tokens so "Ramkund Ghat" still matches "Ramkund" on the token "ramkund".
_PLACE_STOPWORDS = {
    "road", "gate", "circle", "approach", "transit", "parking", "station",
    "chowki", "crossing", "junction", "signal", "chowk", "area", "zone",
    "access", "corridor", "railway", "ghat", "kund", "transit", "near",
    "the", "of", "and", "main", "outer", "belt", "node", "point",
}


def _sig_tokens(text: str) -> set[str]:
    toks = re.split(r"[^a-z0-9]+", text.lower())
    return {t for t in toks if len(t) >= 3 and t not in _PLACE_STOPWORDS}


# --- Geo layer loaders -----------------------------------------------------
def load_zones() -> list[dict]:
    rows = []
    with open(config.ZONES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "zone_name": _clean(r["zone_name"]),
                    "lat": float(r["centroid_lat"]),
                    "lng": float(r["centroid_lng"]),
                    "boundary_points": int(float(r.get("approx_boundary_points") or 0)),
                })
            except (KeyError, ValueError):
                continue
    return rows


def load_cctv() -> list[dict]:
    rows = []
    with open(config.CCTV_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "camera_id": _clean(r["camera_id"]),
                    "lat": float(r["latitude"]),
                    "lng": float(r["longitude"]),
                })
            except (KeyError, ValueError):
                continue
    return rows


def load_police() -> list[dict]:
    rows = []
    with open(config.POLICE_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "station_name": _clean(r["station_name"]),
                    "lat": float(r["latitude"]),
                    "lng": float(r["longitude"]),
                })
            except (KeyError, ValueError):
                continue
    return rows


def load_chokepoints() -> list[dict]:
    rows = []
    with open(config.CHOKEPOINTS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "location_name": _clean(r["location_name"]),
                    "category": _clean(r.get("category")),
                    "lat": float(r["latitude"]),
                    "lng": float(r["longitude"]),
                })
            except (KeyError, ValueError):
                continue
    return rows


# --- Government registry ----------------------------------------------------
def load_government_registry() -> list[dict]:
    """Normalise the synthetic missing-persons CSV into report-shaped dicts."""
    rows = []
    with open(config.MISSING_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "case_id": _clean(r.get("case_id")),
                "source": "government",
                "type": "missing",  # registry rows are reported-missing records
                "reported_at": _clean(r.get("reported_at")),
                "name": _clean(r.get("missing_person_name")),
                "gender": _clean(r.get("gender")) or "Unknown",
                "age_band": _clean(r.get("age_band")),
                "state": _clean(r.get("state")),
                "district": _clean(r.get("district")),
                "language": _clean(r.get("language")),
                "last_seen_location": _clean(r.get("last_seen_location")),
                "reporting_center": _clean(r.get("reporting_center")),
                "reporter_mobile": _clean(r.get("reporter_mobile")),
                "physical_description": _clean(r.get("physical_description")),
                "status": _clean(r.get("status")),
                "is_duplicate_report": _clean(r.get("is_duplicate_report")).lower() == "true",
                "remarks": _clean(r.get("remarks")),
            })
    return rows


# --- Gazetteer + GeoContext ------------------------------------------------
@dataclass
class GeoContext:
    """Geo enrichment for any point or free-text location."""
    zones: list[dict] = field(default_factory=list)
    cctv: list[dict] = field(default_factory=list)
    police: list[dict] = field(default_factory=list)
    chokepoints: list[dict] = field(default_factory=list)
    # name -> (lat, lng) gazetteer built from named places.
    _gazetteer: list[tuple[str, float, float]] = field(default_factory=list)

    @classmethod
    def build(cls) -> "GeoContext":
        ctx = cls(
            zones=load_zones(),
            cctv=load_cctv(),
            police=load_police(),
            chokepoints=load_chokepoints(),
        )
        gaz: list[tuple[str, float, float]] = []
        for p in ctx.chokepoints:
            gaz.append((p["location_name"].lower(), p["lat"], p["lng"]))
        for p in ctx.police:
            gaz.append((p["station_name"].lower(), p["lat"], p["lng"]))
        for z in ctx.zones:
            gaz.append((z["zone_name"].lower(), z["lat"], z["lng"]))
        ctx._gazetteer = gaz
        return ctx

    def resolve_location(self, text: str) -> Optional[tuple[float, float]]:
        """Fuzzy-map a free-text last-seen location to coordinates.

        Combines character similarity, substring containment and *significant
        token* overlap so dataset names like "Ramkund Ghat" resolve to the
        gazetteer's "Ramkund" via the shared token, not just raw edit distance.
        """
        t = _clean(text).lower()
        if not t or not self._gazetteer:
            return None
        t_tokens = _sig_tokens(t)
        best, best_r = None, 0.0
        for name, lat, lng in self._gazetteer:
            r = SequenceMatcher(None, t, name).ratio()
            if name in t or t in name:
                r = max(r, 0.85)
            n_tokens = _sig_tokens(name)
            shared = t_tokens & n_tokens
            # also link morphological variants (Trimbak <-> Trimbakeshwar)
            if not shared and t_tokens and n_tokens:
                shared = {a for a in t_tokens for b in n_tokens
                          if (a.startswith(b) or b.startswith(a))
                          and min(len(a), len(b)) >= 4}
            if shared:
                union = len(t_tokens | n_tokens) or 1
                jac = len(shared) / union
                r = max(r, 0.6 + 0.4 * jac)  # shared identity token => strong
            if r > best_r:
                best, best_r = (lat, lng), r
        return best if best_r >= 0.55 else None

    def enrich(self, lat: Optional[float], lng: Optional[float],
               location_text: str = "") -> dict:
        """Return zone / nearest police / nearby cameras for a point.

        Falls back to resolving `location_text` if no coordinates are given.
        """
        if (lat is None or lng is None) and location_text:
            resolved = self.resolve_location(location_text)
            if resolved:
                lat, lng = resolved
        if lat is None or lng is None:
            return {"resolved": False, "location_text": location_text}

        zone = geo.nearest(lat, lng, self.zones, "lat", "lng")
        station = geo.nearest(lat, lng, self.police, "lat", "lng")
        cams = geo.within(lat, lng, self.cctv, config.CCTV_NEARBY_METERS, "lat", "lng")
        choke = geo.nearest(lat, lng, self.chokepoints, "lat", "lng")
        return {
            "resolved": True,
            "lat": lat,
            "lng": lng,
            "zone": zone["zone_name"] if zone else None,
            "zone_centroid": [zone["lat"], zone["lng"]] if zone else None,
            "nearest_police": station["station_name"] if station else None,
            "nearest_police_distance_m": station["distance_m"] if station else None,
            "cctv_nearby": len(cams),
            "nearest_chokepoint": choke["location_name"] if choke else None,
            "nearest_chokepoint_category": choke["category"] if choke else None,
        }
