"""Cross-pillar data contracts (the artifacts that connect sim <-> planning).

These are plain dataclasses so they serialise to/from JSON with the stdlib only
(no pydantic). Three artifacts matter:

    SituationReport   sim  -> planning   "here is what the crowd is doing"
    DeploymentPlan    planning -> sim    "here is what to deploy" (Claude's output)
    Scorecard         planning -> caller "did the plan beat naive uniform?"

``DEPLOYMENT_PLAN_TOOL_SCHEMA`` is the JSON Schema handed to Claude as a strict
tool so its plan parses deterministically — no free-text parsing.

Coordinates are ``lng``/``lat`` everywhere, matching the CSVs and ``shared.geo``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# Police unit types, by control footprint / function. A "barricade" additionally
# meters flow (caps throughput); constable/squad are repellers of differing radius.
UNIT_TYPES = ("constable", "squad", "barricade")


# --------------------------------------------------------------------------- #
# Situation report (sim -> Claude)
# --------------------------------------------------------------------------- #
@dataclass
class PressurePoint:
    lng: float
    lat: float
    value: float  # crowd pressure = local density * velocity variance (1/s^2-ish)
    t: float      # sim time (s) at which this peak occurred


@dataclass
class SeparationHotspot:
    lng: float
    lat: float
    count: int


@dataclass
class SubzoneDensity:
    name: str
    mean_density: float  # persons / m^2
    peak_density: float


@dataclass
class UnitAvailability:
    station: str
    lng: float
    lat: float
    available: int  # notional deployable units at this station


@dataclass
class CameraState:
    camera_id: str
    lng: float
    lat: float
    heading_deg: float  # current aim, 0 = east, CCW positive
    fov_deg: float
    range_m: float


@dataclass
class SituationReport:
    scenario: str
    corridor_id: str
    t_window_s: float
    pressure_points: list[PressurePoint] = field(default_factory=list)
    separation_hotspots: list[SeparationHotspot] = field(default_factory=list)
    density_summary: list[SubzoneDensity] = field(default_factory=list)
    available_units: list[UnitAvailability] = field(default_factory=list)
    cctv_inventory: list[CameraState] = field(default_factory=list)
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SituationReport":
        return cls(
            scenario=d["scenario"],
            corridor_id=d["corridor_id"],
            t_window_s=d["t_window_s"],
            pressure_points=[PressurePoint(**p) for p in d.get("pressure_points", [])],
            separation_hotspots=[SeparationHotspot(**h) for h in d.get("separation_hotspots", [])],
            density_summary=[SubzoneDensity(**s) for s in d.get("density_summary", [])],
            available_units=[UnitAvailability(**u) for u in d.get("available_units", [])],
            cctv_inventory=[CameraState(**c) for c in d.get("cctv_inventory", [])],
            notes=d.get("notes", ""),
        )


# --------------------------------------------------------------------------- #
# Deployment plan (Claude -> sim)
# --------------------------------------------------------------------------- #
@dataclass
class ForceAllocation:
    unit_type: str  # one of UNIT_TYPES
    lng: float
    lat: float
    rationale: str = ""


@dataclass
class CctvReaim:
    camera_id: str
    heading_deg: float
    rationale: str = ""


@dataclass
class BarrierPlan:
    # A metering line segment, endpoints in geo coords.
    lng1: float
    lat1: float
    lng2: float
    lat2: float
    throughput_cap: float  # persons / second allowed through the gap
    rationale: str = ""


@dataclass
class HelpDesk:
    lng: float
    lat: float
    rationale: str = ""


@dataclass
class DispatchRoute:
    from_station: str
    waypoints: list[list[float]] = field(default_factory=list)  # [[lng,lat], ...]
    purpose: str = ""  # e.g. "dispatch" | "evacuation"
    rationale: str = ""


@dataclass
class DeploymentPlan:
    summary: str = ""
    force_allocations: list[ForceAllocation] = field(default_factory=list)
    cctv_reaims: list[CctvReaim] = field(default_factory=list)
    barriers: list[BarrierPlan] = field(default_factory=list)
    helpdesks: list[HelpDesk] = field(default_factory=list)
    routes: list[DispatchRoute] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DeploymentPlan":
        return cls(
            summary=d.get("summary", ""),
            force_allocations=[ForceAllocation(**f) for f in d.get("force_allocations", [])],
            cctv_reaims=[CctvReaim(**c) for c in d.get("cctv_reaims", [])],
            barriers=[BarrierPlan(**b) for b in d.get("barriers", [])],
            helpdesks=[HelpDesk(**h) for h in d.get("helpdesks", [])],
            routes=[DispatchRoute(**r) for r in d.get("routes", [])],
        )


# --------------------------------------------------------------------------- #
# Scorecard (plan vs naive baseline)
# --------------------------------------------------------------------------- #
@dataclass
class Metrics:
    peak_pressure: float
    total_separations: int
    cctv_coverage: float   # fraction of high-density cells inside some camera cone
    egress_time_s: float   # time for the crowd to clear (or window end if not cleared)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class Scorecard:
    baseline: Metrics            # naive / do-nothing or uniform deployment
    planned: Metrics             # after applying the DeploymentPlan
    composite_baseline: float
    composite_planned: float
    wins: bool                   # planned strictly better on the composite metric
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "baseline": self.baseline.to_dict(),
                "planned": self.planned.to_dict(),
                "composite_baseline": self.composite_baseline,
                "composite_planned": self.composite_planned,
                "wins": self.wins,
                "detail": self.detail,
            },
            indent=2,
        )


# --------------------------------------------------------------------------- #
# JSON Schema for Claude's strict structured output
# --------------------------------------------------------------------------- #
def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


DEPLOYMENT_PLAN_TOOL_SCHEMA: dict[str, Any] = _obj(
    {
        "summary": {"type": "string", "description": "One-paragraph rationale for the overall plan."},
        "force_allocations": {
            "type": "array",
            "description": "Police units to pre-position.",
            "items": _obj(
                {
                    "unit_type": {"type": "string", "enum": list(UNIT_TYPES)},
                    "lng": {"type": "number"},
                    "lat": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                ["unit_type", "lng", "lat", "rationale"],
            ),
        },
        "cctv_reaims": {
            "type": "array",
            "description": "Cameras to re-aim to cover predicted high-density blind spots.",
            "items": _obj(
                {
                    "camera_id": {"type": "string"},
                    "heading_deg": {"type": "number", "description": "0=east, CCW positive, degrees."},
                    "rationale": {"type": "string"},
                },
                ["camera_id", "heading_deg", "rationale"],
            ),
        },
        "barriers": {
            "type": "array",
            "description": "Metering barricade lines that cap flow at a chokepoint.",
            "items": _obj(
                {
                    "lng1": {"type": "number"},
                    "lat1": {"type": "number"},
                    "lng2": {"type": "number"},
                    "lat2": {"type": "number"},
                    "throughput_cap": {"type": "number", "description": "persons/second through the gap"},
                    "rationale": {"type": "string"},
                },
                ["lng1", "lat1", "lng2", "lat2", "throughput_cap", "rationale"],
            ),
        },
        "helpdesks": {
            "type": "array",
            "description": "Kho-Ya-Paya help desks sited at predicted separation hotspots.",
            "items": _obj(
                {"lng": {"type": "number"}, "lat": {"type": "number"}, "rationale": {"type": "string"}},
                ["lng", "lat", "rationale"],
            ),
        },
        "routes": {
            "type": "array",
            "description": "Dispatch / evacuation routes from a police station through waypoints.",
            "items": _obj(
                {
                    "from_station": {"type": "string"},
                    "waypoints": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "Ordered [lng, lat] waypoints.",
                    },
                    "purpose": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                ["from_station", "waypoints", "purpose", "rationale"],
            ),
        },
    },
    ["summary", "force_allocations", "cctv_reaims", "barriers", "helpdesks", "routes"],
)
