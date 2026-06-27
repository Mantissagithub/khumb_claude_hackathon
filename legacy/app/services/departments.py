"""
Single source of truth for the departments that handle devotee issues at the
Kumbh Mela. The Claude routing engine, the assignment validation, and the admin
dashboard all read from this registry, so adding a department here makes it
available everywhere.

If you add or rename a key, also update the `DepartmentCode` Literal in
app/models/issue.py (kept in sync by the assertion at the bottom of this file).
"""

DEPARTMENTS: dict[str, dict] = {
    "LOST_AND_FOUND": {
        "name": "Lost & Found / Missing Persons Cell",
        "description": "Lost or missing people, separated children, lost elderly "
        "pilgrims, reuniting families, and lost belongings/documents.",
        "contact_email": "lostfound.control@kumbh.gov.in",
        "contact_phone": "1920",
    },
    "MEDICAL": {
        "name": "Medical & Emergency Response",
        "description": "Injuries, illness, collapses, heat stroke, cardiac events, "
        "pregnancy emergencies, ambulance dispatch, and first-aid needs.",
        "contact_email": "medical.control@kumbh.gov.in",
        "contact_phone": "108",
    },
    "POLICE_SECURITY": {
        "name": "Police & Security",
        "description": "Theft, pickpocketing, fraud, harassment, assault, lost-and-"
        "stolen reports, suspicious persons or objects, and general law & order.",
        "contact_email": "police.control@kumbh.gov.in",
        "contact_phone": "112",
    },
    "FIRE_SAFETY": {
        "name": "Fire & Hazard Safety",
        "description": "Fire, smoke, gas leaks, electrical hazards, and any "
        "immediate fire-risk situations in tents, kitchens, or stalls.",
        "contact_email": "fire.control@kumbh.gov.in",
        "contact_phone": "101",
    },
    "CROWD_CONTROL": {
        "name": "Crowd Management & Safety",
        "description": "Overcrowding, stampede risk, dangerous congestion at ghats, "
        "bridges and chokepoints, and crowd diversion needs.",
        "contact_email": "crowd.control@kumbh.gov.in",
        "contact_phone": "1944",
    },
    "SANITATION": {
        "name": "Sanitation & Hygiene",
        "description": "Dirty or overflowing toilets, garbage, water-logging, "
        "drainage, and general cleanliness complaints.",
        "contact_email": "sanitation.control@kumbh.gov.in",
        "contact_phone": "1800-XXXXXX",
    },
    "INFRASTRUCTURE": {
        "name": "Infrastructure & Utilities",
        "description": "Water supply, electricity, lighting, tents/shelters, roads, "
        "barricades, signage, and other physical facilities.",
        "contact_email": "infra.control@kumbh.gov.in",
        "contact_phone": "1800-YYYYYY",
    },
    "GENERAL_HELPDESK": {
        "name": "General Help Desk",
        "description": "Directions, schedule and ritual information, general "
        "queries, and anything that does not fit a specialised department.",
        "contact_email": "helpdesk.control@kumbh.gov.in",
        "contact_phone": "1100",
    },
}

# Ordered list of valid department codes — used for validation and the prompt.
DEPARTMENT_CODES: list[str] = list(DEPARTMENTS.keys())


def department_catalog_for_prompt() -> str:
    """Render the department list as a compact catalog for the Claude prompt."""
    lines = []
    for code, meta in DEPARTMENTS.items():
        lines.append(f"- {code} ({meta['name']}): {meta['description']}")
    return "\n".join(lines)


def is_valid_department(code: str) -> bool:
    return code in DEPARTMENTS
