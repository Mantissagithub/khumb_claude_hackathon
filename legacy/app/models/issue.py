"""
Pydantic schemas for the issue/ticket lifecycle.

`AIAnalysis` doubles as the structured-output schema we hand to Claude via
`client.messages.parse(...)` — Claude is forced to return exactly these fields,
validated, so the admin dashboard always gets a clean suggestion.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

# Keep this Literal in sync with app/services/departments.DEPARTMENTS.
DepartmentCode = Literal[
    "LOST_AND_FOUND",
    "MEDICAL",
    "POLICE_SECURITY",
    "FIRE_SAFETY",
    "CROWD_CONTROL",
    "SANITATION",
    "INFRASTRUCTURE",
    "GENERAL_HELPDESK",
]

Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

TicketStatus = Literal["NEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED"]


class AIAnalysis(BaseModel):
    """The structured suggestion Claude returns for each raised issue."""

    summary: str = Field(
        description="A short, clear one-line title for the issue (max ~12 words), "
        "ALWAYS written in English for the admin dashboard — translate if needed."
    )
    language: str = Field(
        default="English",
        description="The language the report was written in, e.g. 'English', "
        "'Hindi', 'Marathi', 'Telugu', 'Maithili'.",
    )
    suggested_department: DepartmentCode = Field(
        description="The single most relevant department to handle this issue."
    )
    priority: Priority = Field(
        description="Urgency. CRITICAL = life-threatening / stampede / fire; "
        "HIGH = urgent but not life-threatening; MEDIUM = needs attention soon; "
        "LOW = routine."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident you are in the department suggestion (0-1).",
    )
    reasoning: str = Field(
        description="One or two sentences explaining the routing decision, for the admin."
    )
    recommended_action: str = Field(
        description="The single most important immediate step the department should take. "
        "When a nearby asset is relevant, name it (e.g. the nearest hospital/booth)."
    )
    nearest_asset: Optional[str] = Field(
        default=None,
        description="The single most relevant nearby asset from the provided list, if any.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="A few short keyword tags (e.g. 'child', 'theft', 'ghat').",
    )


# ----- API request / response shapes -----

class IssueCreate(BaseModel):
    """Payload a devotee/volunteer submits to raise an issue."""

    description: str = Field(min_length=3, description="What is the problem?")
    reporter_name: Optional[str] = Field(default=None)
    reporter_contact: Optional[str] = Field(default=None)
    zone: Optional[str] = Field(
        default=None, description="Sector / ghat / landmark, e.g. 'Sector 7, Sangam Ghat'."
    )


class AssignRequest(BaseModel):
    department: DepartmentCode
    assigned_by: Optional[str] = Field(default="admin")


class Ticket(BaseModel):
    """The full ticket as stored in the ledger and shown on the dashboard."""

    ticket_id: str
    description: str
    reporter_name: Optional[str] = None
    reporter_contact: Optional[str] = None
    zone: Optional[str] = None
    created_at: str
    status: TicketStatus = "NEW"

    ai_analysis: Optional[AIAnalysis] = None
    ai_engine: str = "claude"  # "claude" or "fallback" (keyword heuristic)

    assigned_department: Optional[DepartmentCode] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[str] = None

    # --- Duplicate detection / auto-merge ---
    # How many separate reports have been folded into this ticket (1 = original).
    report_count: int = 1
    # Brief record of each merged duplicate report.
    merged_reports: list[dict] = Field(default_factory=list)


class IssueResponse(BaseModel):
    """Returned when an issue is raised — tells the client whether the report
    created a new ticket or was merged into an existing (duplicate) one."""

    merged: bool = Field(
        description="True if this report was merged into an existing ticket."
    )
    ticket: Ticket
    message: str
