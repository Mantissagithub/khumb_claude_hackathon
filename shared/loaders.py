"""Single source of truth for reading ``data/data/*.csv``.

Every module that needs the real Nashik geography goes through here — no ad-hoc
``csv.reader`` calls scattered across the codebase (CLAUDE.md: "Data loading: go
through ``shared/`` loaders"). Coordinates are returned as ``(lng, lat)`` tuples.

Uses only the stdlib ``csv`` module so there is no pandas dependency in the sim path.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# data/data lives two levels under the repo root: <root>/data/data/*.csv
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "data"


@dataclass(frozen=True)
class Zone:
    name: str
    lng: float
    lat: float
    boundary_points: int


@dataclass(frozen=True)
class Chokepoint:
    name: str
    category: str  # e.g. "Traffic choke point", "Transfer node", "Parking", ...
    lng: float
    lat: float


@dataclass(frozen=True)
class PoliceStation:
    name: str
    lng: float
    lat: float


@dataclass(frozen=True)
class Camera:
    camera_id: str
    zone: str  # derived from the "Z<n>-C<m>" id prefix
    lng: float
    lat: float


def _rows(filename: str) -> list[dict[str, str]]:
    path = DATA_DIR / filename
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_zones() -> list[Zone]:
    return [
        Zone(
            name=r["zone_name"],
            lng=float(r["centroid_lng"]),
            lat=float(r["centroid_lat"]),
            boundary_points=int(r["approx_boundary_points"]),
        )
        for r in _rows("Zone_Boundaries.csv")
    ]


def load_chokepoints() -> list[Chokepoint]:
    out: list[Chokepoint] = []
    for r in _rows("Chokepoints_Parking.csv"):
        # One source row has a stray quoted comma; csv handles quoting, but guard
        # against any row missing numeric coords rather than crashing the loader.
        try:
            out.append(
                Chokepoint(
                    name=r["location_name"],
                    category=r["category"],
                    lng=float(r["longitude"]),
                    lat=float(r["latitude"]),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def load_police_stations() -> list[PoliceStation]:
    return [
        PoliceStation(name=r["station_name"], lng=float(r["longitude"]), lat=float(r["latitude"]))
        for r in _rows("Police_Stations.csv")
    ]


def load_cameras() -> list[Camera]:
    out: list[Camera] = []
    for r in _rows("CCTV_Locations.csv"):
        cid = r["camera_id"]
        zone = cid.split("-", 1)[0] if "-" in cid else ""
        out.append(Camera(camera_id=cid, zone=zone, lng=float(r["longitude"]), lat=float(r["latitude"])))
    return out


def load_missing_persons() -> list[dict[str, str]]:
    """Raw synthetic missing-person rows (15% no name, 8% cross-center dupes).

    Returned as dicts — the registry/matching pillar owns the typed schema. The
    sim only uses these as a *prior* for where separations historically cluster
    (the ``last_seen_location`` field), so dicts are sufficient here.
    """
    return _rows("Synthetic_Missing_Persons_2500.csv")
