"""
Request / response schemas for the KumbhSeva HTTP API.

These mirror the ticket dicts that flow through app/services/* (and the Supabase
`tickets` table). Tickets themselves are returned as open dicts (extra="allow")
so any column the store carries reaches the frontend untouched; the typed fields
just give nice OpenAPI docs.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ResponderDept = Literal["POLICE", "MEDICAL", "FIRE_BRIGADE"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Dispatch lifecycle (index = dispatch_stage). Mirrors STAGES in streamlit_app.py.
STAGES = ["Reported", "Dispatched", "En route", "On-site", "Resolved"]


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class IssueCreate(BaseModel):
    """A citizen report. Only `description` is required; everything else helps
    the AI route it and locate the nearest responder centre."""

    description: str = Field(min_length=1, description="Free text, any language.")
    zone: Optional[str] = Field(default=None, description="Zone / landmark, e.g. 'Sector 7'.")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_b64: Optional[str] = Field(default=None, description="Base64-encoded photo bytes.")
    photo_url: Optional[str] = Field(default=None, description="URL to a hosted photo.")
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None


class TriageRequest(BaseModel):
    """Run the AI triage on a description WITHOUT persisting a ticket — useful for
    a live preview in the report form."""

    description: str = Field(min_length=1)
    zone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AssignRequest(BaseModel):
    department: ResponderDept = Field(description="Responder to dispatch to.")


class DispatchRequest(BaseModel):
    stage: int = Field(ge=0, le=len(STAGES) - 1,
                       description=f"0..{len(STAGES) - 1} → {', '.join(STAGES)}.")


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class Ticket(BaseModel):
    """Open ticket record — typed fields are documented, extras pass through."""

    model_config = ConfigDict(extra="allow")

    ticket_id: str
    description: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    department: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    recommended_action: Optional[str] = None
    nearest_asset: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: Optional[str] = None
    dispatch_stage: Optional[int] = None
    assigned_department: Optional[str] = None
    zone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None
    ai_engine: Optional[str] = None
    created_at: Optional[str] = None
    assigned_at: Optional[str] = None


class TriageResponse(BaseModel):
    """The AI suggestion plus which engine produced it ('claude' or 'fallback')."""

    model_config = ConfigDict(extra="allow")

    summary: str
    language: str
    department: ResponderDept
    priority: Priority
    confidence: float
    reasoning: str
    recommended_action: str
    nearest_asset: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    ai_engine: str


class Department(BaseModel):
    code: ResponderDept
    name: str
    emoji: str
    scope: str


class ResponderCentre(BaseModel):
    department: ResponderDept
    suggested: bool = Field(description="True if the AI routed the ticket here.")
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    zone: Optional[str] = None
    distance_km: Optional[float] = None


class Health(BaseModel):
    status: str
    ai_engine: str
    storage: str
    model: str
    stages: list[str]
