"""Thin Claude client that turns a SituationReport into a DeploymentPlan.

Uses the Messages API with a single strict tool, so Claude's plan parses
deterministically against ``shared.schema`` — no free-text parsing. Credentials
resolve the standard way (``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` /
``ant auth`` profile); if none is configured, callers fall back to the local
heuristic planner (``planning.naive.heuristic_plan``).
"""

from __future__ import annotations

import anthropic

from shared.schema import DEPLOYMENT_PLAN_TOOL_SCHEMA, DeploymentPlan, SituationReport

MODEL = "claude-opus-4-8"

SYSTEM = """You are the deployment planner for Setu, the crowd-safety command platform for the \
Nashik-Trimbakeshwar Simhastha Kumbh Mela 2027. You are given a SituationReport from a behavioral \
crowd simulation over a real ghat-approach corridor: predicted crowd-pressure points, family \
separation hotspots, per-subzone density, the CCTV inventory (with current aim), and the police \
units available at each station.

Produce a deployment plan that, compared to spreading the same resources uniformly:
  - re-aims cameras (heading, 0=east CCW+) to cover the highest-pressure points and separation \
hotspots that are currently blind;
  - places police units (constable=small footprint, squad=larger, barricade=metering gate) to \
organize the highest-pressure zones; put barricades UPSTREAM of a narrowing in a wide area so the \
held crowd has room to spread (hold-and-release), never inside the narrow throat itself;
  - sites Kho-Ya-Paya help desks at the separation hotspots;
  - gives nearest-unit dispatch / evacuation routes from the closest stations to the danger zones.

Be specific and grounded in the report's coordinates. Always call submit_deployment_plan."""

_TOOL = {
    "name": "submit_deployment_plan",
    "description": "Submit the force/CCTV/barrier/help-desk/route deployment plan for this corridor.",
    "strict": True,
    "input_schema": DEPLOYMENT_PLAN_TOOL_SCHEMA,
}


def claude_plan(report: SituationReport, max_tokens: int = 8000) -> DeploymentPlan:
    """Call Claude and return its structured DeploymentPlan. Raises on no key."""
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "submit_deployment_plan"},
        messages=[{
            "role": "user",
            "content": (
                "Here is the situation report. Plan the deployment for this corridor.\n\n"
                + report.to_json()
            ),
        }],
    )
    for block in msg.content:
        if block.type == "tool_use" and block.name == "submit_deployment_plan":
            return DeploymentPlan.from_dict(block.input)
    raise RuntimeError("Claude did not return a deployment plan")
