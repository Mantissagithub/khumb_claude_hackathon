"""
Triage engine for the Streamlit control-room demo.

Routes each report to one of THREE emergency responders — Police, Medical, or
Fire Brigade — and returns a structured suggestion (English summary + original
language + priority + reasoning + recommended action + nearest asset).

Unlike app/services/claude_engine.py (which reads the key from .env and uses the
full 8-department catalog), this version takes the API key as an argument so the
Streamlit UI can supply it at runtime, and narrows the choices to the three
responders the admin assigns to.
"""

import re
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from app.services.knowledge_graph import nearest_responder_asset

ResponderDept = Literal["POLICE", "MEDICAL", "FIRE_BRIGADE"]

RESPONDERS: dict[str, dict] = {
    "POLICE": {"name": "Police", "emoji": "🚓",
               "scope": "theft, crime, missing/lost persons, harassment, fights, "
                        "suspicious activity, crowd/security and general law & order."},
    "MEDICAL": {"name": "Medical", "emoji": "🚑",
                "scope": "injuries, illness, collapses, breathing/cardiac issues, "
                         "heat stroke, pregnancy emergencies and any first-aid need."},
    "FIRE_BRIGADE": {"name": "Fire Brigade", "emoji": "🚒",
                     "scope": "fire, smoke, gas leaks, electrical hazards and any "
                              "fire-risk situation."},
}


class TriageResult(BaseModel):
    summary: str = Field(description="Short one-line title in ENGLISH (translate if needed).")
    language: str = Field(default="English", description="Original language of the report.")
    department: ResponderDept = Field(description="Best responder: POLICE, MEDICAL, or FIRE_BRIGADE.")
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="One sentence justifying the routing, for the admin.")
    recommended_action: str = Field(description="The single most important immediate step.")
    nearest_asset: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)


def _system_prompt() -> str:
    catalog = "\n".join(
        f"- {code} ({m['name']}): {m['scope']}" for code, m in RESPONDERS.items()
    )
    return (
        "You are the triage brain for KumbhSeva, the emergency control room for "
        "the Kumbh Mela. A pilgrim has reported a problem. Route it to ONE of "
        "these three responders:\n"
        f"{catalog}\n\n"
        "Rules:\n"
        "- Pick exactly one department.\n"
        "- Be decisive about priority: fire/stampede/life-threatening = CRITICAL; "
        "lost child or medical issue = at least HIGH.\n"
        "- Pilgrims may write in Marathi, Telugu, Maithili, Hindi, etc. ALWAYS "
        "write summary/reasoning/recommended_action in ENGLISH for the admin, but "
        "set `language` to the original language of the report.\n"
        "- Keep everything short and operational — the admin triages dozens fast."
    )


def classify(
    description: str,
    api_key: str | None,
    model: str = "claude-opus-4-8",
    zone: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[dict, str]:
    """Returns (result_dict, engine) where engine is 'claude' or 'fallback'."""
    result: TriageResult
    engine: str

    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            user = f"Issue report: {description}"
            if zone:
                user += f"\nReported zone: {zone}"
            response = client.messages.parse(
                model=model,
                max_tokens=1024,
                system=_system_prompt(),
                messages=[{"role": "user", "content": user}],
                output_format=TriageResult,
            )
            result = response.parsed_output  # type: ignore[assignment]
            engine = "claude"
            if result is None:
                result, engine = _fallback(description), "fallback"
        except Exception as exc:  # noqa: BLE001
            print(f"[KumbhSeva] triage via Claude failed, using fallback: {exc}")
            result, engine = _fallback(description), "fallback"
    else:
        result, engine = _fallback(description), "fallback"

    # Ground the nearest asset in the knowledge graph (deterministic).
    result.nearest_asset = nearest_responder_asset(result.department, lat, lon, zone)
    return result.model_dump(), engine


# --------------------------------------------------------------------------- #
# Keyword fallback (no API key) — safety net only; Claude is the real brain.
# --------------------------------------------------------------------------- #

_KW = [
    ("FIRE_BRIGADE", ["fire", "smoke", "burning", "gas leak", "flame", "spark"], "CRITICAL"),
    ("MEDICAL", ["injur", "blood", "unconscious", "faint", "heart", "breath",
                 "sick", "ill", "ambulance", "medical", "pregnan", "collapse"], "HIGH"),
    ("POLICE", ["theft", "stolen", "robber", "pickpocket", "fraud", "harass",
                "assault", "fight", "suspicious", "weapon", "lost", "missing",
                "child", "crowd", "stampede"], "HIGH"),
]


def _hit(k: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(k), text) is not None


def _fallback(description: str) -> TriageResult:
    text = description.lower()
    for dept, kws, prio in _KW:
        if any(_hit(k, text) for k in kws):
            return TriageResult(
                summary=description[:80],
                language="Unknown (fallback)",
                department=dept,  # type: ignore[arg-type]
                priority=prio,  # type: ignore[arg-type]
                confidence=0.4,
                reasoning="Keyword-based fallback (no Claude API key set).",
                recommended_action="Review and dispatch the relevant team.",
                tags=[k for _, ks, _ in _KW for k in ks if _hit(k, text)][:4],
            )
    return TriageResult(
        summary=description[:80],
        language="Unknown (fallback)",
        department="POLICE",
        priority="MEDIUM",
        confidence=0.3,
        reasoning="No clear keywords — defaulting to Police control for triage.",
        recommended_action="Manually triage and dispatch.",
        tags=[],
    )
