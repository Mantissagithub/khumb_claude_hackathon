"""Geography helpers grounded in the provided location datasets.

We only have zone *centroids* (not full polygons), so zone assignment is
nearest-centroid. That is accurate enough to (a) bucket reports for blocking
and (b) tell an operator the zone, nearest police station and nearby CCTV
for any reported / found location.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two lat/lng points."""
    r = 6_371_000.0  # earth radius, metres
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def nearest(lat: float, lng: float, points: Iterable[dict],
            lat_key: str = "lat", lng_key: str = "lng") -> Optional[dict]:
    """Return the point dict closest to (lat, lng), with a `distance_m` field."""
    best, best_d = None, float("inf")
    for p in points:
        try:
            d = haversine_m(lat, lng, float(p[lat_key]), float(p[lng_key]))
        except (KeyError, TypeError, ValueError):
            continue
        if d < best_d:
            best, best_d = p, d
    if best is None:
        return None
    out = dict(best)
    out["distance_m"] = round(best_d, 1)
    return out


def within(lat: float, lng: float, points: Iterable[dict], radius_m: float,
           lat_key: str = "lat", lng_key: str = "lng") -> list[dict]:
    """All points within `radius_m`, each annotated with `distance_m`, nearest first."""
    hits = []
    for p in points:
        try:
            d = haversine_m(lat, lng, float(p[lat_key]), float(p[lng_key]))
        except (KeyError, TypeError, ValueError):
            continue
        if d <= radius_m:
            q = dict(p)
            q["distance_m"] = round(d, 1)
            hits.append(q)
    hits.sort(key=lambda x: x["distance_m"])
    return hits
