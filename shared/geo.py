"""Geographic <-> local-metric projection.

The simulation runs its physics in metres, but every CSV in ``data/data`` stores
points as ``(longitude, latitude)`` and AGENTS.md requires we keep that ordering.
This module is the single place that converts between the two.

We use a local equirectangular (equidistant-cylindrical) projection anchored at a
reference point. Over a corridor a few hundred metres across at Nashik's latitude
the distortion is well under a metre, which is far below the ~0.25 m agent radius —
good enough for a microscopic crowd model, and cheap (no pyproj dependency).

Convention used throughout the codebase:
    * geographic coordinates are passed and stored as ``(lng, lat)`` tuples
    * metric coordinates are ``(x, y)`` in metres, x = east, y = north
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# WGS-84 metres per degree of latitude (very nearly constant).
_M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class LocalProjection:
    """Equirectangular projection about an anchor ``(lng, lat)``.

    Build once per corridor (the anchor is the corridor's reference point), then
    use :meth:`to_xy` / :meth:`to_lnglat` everywhere. Round-trips to sub-millimetre.
    """

    anchor_lng: float
    anchor_lat: float

    @property
    def _m_per_deg_lng(self) -> float:
        return _M_PER_DEG_LAT * math.cos(math.radians(self.anchor_lat))

    def to_xy(self, lng: float, lat: float) -> tuple[float, float]:
        """``(lng, lat)`` degrees -> ``(x, y)`` metres east/north of the anchor."""
        x = (lng - self.anchor_lng) * self._m_per_deg_lng
        y = (lat - self.anchor_lat) * _M_PER_DEG_LAT
        return x, y

    def to_lnglat(self, x: float, y: float) -> tuple[float, float]:
        """``(x, y)`` metres -> ``(lng, lat)`` degrees."""
        lng = self.anchor_lng + x / self._m_per_deg_lng
        lat = self.anchor_lat + y / _M_PER_DEG_LAT
        return lng, lat


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Great-circle distance in metres between two ``(lng, lat)`` points.

    Used for sanity checks and for distances that span more than one corridor
    (e.g. police-station to chokepoint), where the local projection's anchor
    would no longer be valid.
    """
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
