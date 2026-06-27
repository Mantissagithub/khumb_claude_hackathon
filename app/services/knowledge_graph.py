"""
Lightweight knowledge graph of on-ground assets at the Mela.

Each asset carries a centre code and GPS coordinates, so when a citizen's report
includes their location we can compute the nearest relevant responder centre
(hospital / police tent / fire station) — its name, code and distance.

This is the seed for the full graph (cases / zones / CCTV / police /
chokepoints) and the chokepoint-avoiding route planner that comes next.
"""

from math import asin, cos, radians, sin, sqrt

# Coordinates are around Prayagraj Sangam (fictional but plausible).
ASSETS: list[dict] = [
    {"code": "HOSP-01", "name": "Central Civil Hospital", "type": "HOSPITAL", "zone": "Sector 1", "lat": 25.4280, "lon": 81.8870},
    {"code": "HOSP-02", "name": "Sangam Ghat First-Aid Post", "type": "HOSPITAL", "zone": "Sangam Ghat", "lat": 25.4225, "lon": 81.8836},
    {"code": "HOSP-03", "name": "Sector 7 Medical Camp", "type": "HOSPITAL", "zone": "Sector 7", "lat": 25.4350, "lon": 81.8790},
    {"code": "POL-01", "name": "Police Control Tent A", "type": "POLICE_TENT", "zone": "Sector 4", "lat": 25.4300, "lon": 81.8810},
    {"code": "POL-02", "name": "Sangam Ghat Police Outpost", "type": "POLICE_TENT", "zone": "Sangam Ghat", "lat": 25.4230, "lon": 81.8845},
    {"code": "POL-03", "name": "Sector 9 Police Outpost", "type": "POLICE_TENT", "zone": "Sector 9", "lat": 25.4390, "lon": 81.8750},
    {"code": "FIRE-01", "name": "Fire Station North", "type": "FIRE_STATION", "zone": "Sector 2", "lat": 25.4310, "lon": 81.8895},
    {"code": "FIRE-02", "name": "Fire Post - Mela Bazaar", "type": "FIRE_STATION", "zone": "Mela Bazaar", "lat": 25.4265, "lon": 81.8780},
    {"code": "LF-01", "name": "Lost & Found Booth - Sector 4", "type": "LOST_FOUND_BOOTH", "zone": "Sector 4", "lat": 25.4298, "lon": 81.8815},
    {"code": "SAN-01", "name": "Sanitation Block S7", "type": "SANITATION_BLOCK", "zone": "Sector 7", "lat": 25.4345, "lon": 81.8795},
    {"code": "HELP-01", "name": "Help Desk - Main Gate", "type": "HELP_DESK", "zone": "Main Gate", "lat": 25.4255, "lon": 81.8900},
    {"code": "CCT-01", "name": "Crowd Control Tower - Ram Ghat Bridge", "type": "CROWD_TOWER", "zone": "Ram Ghat Bridge", "lat": 25.4240, "lon": 81.8860},
]

# Map a responder department to the asset type it would be dispatched from.
DEPARTMENT_ASSET_TYPE = {
    "MEDICAL": "HOSPITAL",
    "POLICE": "POLICE_TENT",
    "FIRE_BRIGADE": "FIRE_STATION",
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest_asset_detail(
    department: str,
    lat: float | None = None,
    lon: float | None = None,
    zone: str | None = None,
) -> dict | None:
    """Return {code, name, type, zone, distance_km} for the nearest centre of the
    department's responder type, by coords if available, else fuzzy zone, else
    the first of that type. distance_km is None when coordinates are unknown."""
    asset_type = DEPARTMENT_ASSET_TYPE.get(department)
    if not asset_type:
        return None
    pool = [a for a in ASSETS if a["type"] == asset_type]
    if not pool:
        return None

    if lat is not None and lon is not None:
        nearest = min(pool, key=lambda a: _haversine_km(lat, lon, a["lat"], a["lon"]))
        dist = _haversine_km(lat, lon, nearest["lat"], nearest["lon"])
        return {**nearest, "distance_km": round(dist, 2)}

    if zone:
        z = zone.lower()
        for a in pool:
            if a["zone"].lower() in z:
                return {**a, "distance_km": None}
    return {**pool[0], "distance_km": None}


def nearest_responder_asset(
    department: str,
    lat: float | None = None,
    lon: float | None = None,
    zone: str | None = None,
) -> str | None:
    """Nearest centre as a display string (used by the main triage flow)."""
    detail = nearest_asset_detail(department, lat, lon, zone)
    if not detail:
        return None
    if detail.get("distance_km") is not None:
        return f"{detail['name']} ({detail['code']}, ~{detail['distance_km']} km)"
    return f"{detail['name']} ({detail['code']})"


def nearby_assets(zone: str | None) -> list[dict]:
    """Assets whose zone is mentioned in the reported location string."""
    if not zone:
        return ASSETS[:3]
    z = zone.lower()
    matched = [a for a in ASSETS if a["zone"].lower() in z]
    return matched or ASSETS[:3]


def assets_for_prompt(zone: str | None) -> str:
    assets = nearby_assets(zone)
    if not assets:
        return "No mapped assets near this location."
    return "\n".join(f"- {a['name']} ({a['type']}, {a['zone']})" for a in assets)
