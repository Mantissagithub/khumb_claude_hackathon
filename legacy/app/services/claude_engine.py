"""
The AI routing brain.

When a devotee raises an issue, the raw description is sent to Claude, which
returns a structured `AIAnalysis` (department + priority + reasoning + action).
The admin sees this suggestion on the ticket and can assign with one click.

We use `client.messages.parse(...)` with `output_format=AIAnalysis` so Claude is
constrained to return exactly our schema — no brittle text parsing.

If no ANTHROPIC_API_KEY is configured (or the call fails), we fall back to a
simple keyword heuristic so the prototype still works end-to-end for testing.
"""

import re

import anthropic

from app.core.config import settings
from app.models.issue import AIAnalysis
from app.services.departments import (
    department_catalog_for_prompt,
    is_valid_department,
)
from app.services.knowledge_graph import assets_for_prompt

SYSTEM_PROMPT = """You are the triage brain for KumbhSeva, the issue-routing \
system for the Kumbh Mela — one of the largest human gatherings on earth, with \
tens of millions of pilgrims (devotees).

A devotee, volunteer, or officer has just reported a problem. Your job is to \
read the report and route it to the single most relevant department so the \
admin control room can dispatch help with minimal investigation.

The available departments are:
{catalog}

Rules:
- Pick exactly ONE suggested_department from the codes above.
- Be decisive about priority. Anything that threatens life or could cause a \
stampede/fire is CRITICAL. A lost child or a medical issue is at least HIGH.
- Keep summary, reasoning, and recommended_action short and operational — the \
admin is reading dozens of these under time pressure.
- If the report is vague or purely informational, use GENERAL_HELPDESK with \
lower priority.

Language:
- Pilgrims may report in Marathi, Telugu, Maithili, Hindi, or other languages. \
ALWAYS write the summary (and reasoning/recommended_action) in ENGLISH so the \
admin team can read it, but set the `language` field to the original language of \
the report. This breaks the language barrier for the control room.

Nearby assets (knowledge graph):
- You will be given a short list of on-ground assets near the reported location. \
When relevant, name the single most useful one in `recommended_action` and put \
it in `nearest_asset` (e.g. direct a lost child to the nearest Lost & Found \
booth, or an injury to the nearest hospital/first-aid post). If none are \
relevant, leave nearest_asset null."""


def _build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(catalog=department_catalog_for_prompt())


def _user_message(description: str, zone: str | None) -> str:
    parts = [f"Issue report: {description}"]
    if zone:
        parts.append(f"Reported location/zone: {zone}")
    parts.append("\nNearby assets near this location:")
    parts.append(assets_for_prompt(zone))
    return "\n".join(parts)


def analyze_with_claude(description: str, zone: str | None = None) -> tuple[AIAnalysis, str]:
    """
    Returns (analysis, engine) where engine is 'claude' or 'fallback'.
    Never raises — always returns a usable suggestion so a ticket can be created.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _keyword_fallback(description), "fallback"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": _user_message(description, zone)}],
            output_format=AIAnalysis,
        )
        analysis = response.parsed_output
        # Defensive: guarantee a valid department even if the model drifts.
        if analysis is None or not is_valid_department(analysis.suggested_department):
            return _keyword_fallback(description, zone), "fallback"
        return analysis, "claude"
    except Exception as exc:  # noqa: BLE001 — never break ticket creation
        print(f"[KumbhSeva] Claude routing failed, using fallback: {exc}")
        return _keyword_fallback(description, zone), "fallback"


# --------------------------------------------------------------------------- #
# Keyword fallback — a deliberately simple heuristic so the system is usable
# without an API key. Claude is the real engine; this is only a safety net.
# --------------------------------------------------------------------------- #

_KEYWORDS: list[tuple[str, list[str], str]] = [
    # (department, keywords, default priority)
    ("MEDICAL", ["injur", "blood", "unconscious", "faint", "heart", "breath",
                 "sick", "ill", "ambulance", "medical", "pregnan", "collapse"], "HIGH"),
    ("LOST_AND_FOUND", ["lost", "missing", "child", "kid", "son", "daughter",
                        "separated", "can't find", "cant find", "wandered"], "HIGH"),
    ("FIRE_SAFETY", ["fire", "smoke", "burning", "gas leak", "spark", "flame"], "CRITICAL"),
    ("CROWD_CONTROL", ["stampede", "crowd", "crush", "overcrowd", "congest",
                       "push", "pile up", "too many people"], "CRITICAL"),
    ("POLICE_SECURITY", ["theft", "stolen", "robber", "pickpocket", "fraud",
                         "harass", "assault", "fight", "suspicious", "weapon"], "HIGH"),
    ("SANITATION", ["toilet", "garbage", "dirty", "waste", "drain", "smell",
                    "sewage", "water logg", "unhygienic"], "MEDIUM"),
    ("INFRASTRUCTURE", ["water supply", "electricity", "power", "light", "tent",
                        "road", "barricade", "sign", "leak"], "MEDIUM"),
]


def _kw_hit(keyword: str, text: str) -> bool:
    # Word-boundary (prefix) match so 'ill' doesn't fire on 'spilling'.
    return re.search(r"\b" + re.escape(keyword), text) is not None


def _keyword_fallback(description: str, zone: str | None = None) -> AIAnalysis:
    from app.services.knowledge_graph import nearby_assets

    assets = nearby_assets(zone)
    nearest = assets[0]["name"] if assets else None
    text = description.lower()
    for dept, keywords, priority in _KEYWORDS:
        if any(_kw_hit(k, text) for k in keywords):
            return AIAnalysis(
                summary=description[:80],
                language="Unknown (fallback)",
                suggested_department=dept,  # type: ignore[arg-type]
                priority=priority,  # type: ignore[arg-type]
                confidence=0.4,
                reasoning="Keyword-based fallback (no Claude API key configured).",
                recommended_action="Review and dispatch the relevant on-ground team.",
                nearest_asset=nearest,
                tags=[k for _, ks, _ in _KEYWORDS for k in ks if _kw_hit(k, text)][:4],
            )
    return AIAnalysis(
        summary=description[:80],
        language="Unknown (fallback)",
        suggested_department="GENERAL_HELPDESK",
        priority="LOW",
        confidence=0.3,
        reasoning="No specific keywords matched (fallback heuristic).",
        recommended_action="Triage manually and route to the appropriate desk.",
        nearest_asset=nearest,
        tags=[],
    )
