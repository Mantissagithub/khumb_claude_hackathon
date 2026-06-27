"""Pilgrim agent types and family-party generation.

The at-risk groups Setu exists to protect — children, the elderly, the
mobility-impaired, and the families that bind them — are modelled explicitly,
because *who* gets separated and *where* is the whole point (AGENTS.md §1).

Each type carries Social-Force-Model physical parameters; parties carry the group
structure (a guardian + dependents) whose bond can break under crowd pressure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AgentParams:
    name: str
    v0: float        # desired (free-flow) walking speed, m/s
    mass: float      # kg — scales contact/crush forces
    radius: float    # m — torso radius
    fall_risk: float # relative susceptibility to being trampled when crushed (0..1)


# Type table (Helbing-style speeds; masses/radii from pedestrian-dynamics literature).
AGENT_PARAMS: dict[str, AgentParams] = {
    "adult_normal":      AgentParams("adult_normal",      v0=1.30, mass=70.0, radius=0.25, fall_risk=0.15),
    "child":             AgentParams("child",             v0=0.90, mass=25.0, radius=0.18, fall_risk=0.85),
    "elderly":           AgentParams("elderly",           v0=0.80, mass=60.0, radius=0.25, fall_risk=0.75),
    "mobility_impaired": AgentParams("mobility_impaired", v0=0.50, mass=80.0, radius=0.35, fall_risk=0.90),
}

TYPE_NAMES: list[str] = list(AGENT_PARAMS.keys())
TYPE_IDS: dict[str, int] = {n: i for i, n in enumerate(TYPE_NAMES)}

# Stacked parameter arrays indexed by type id (for the vectorised engine).
V0 = np.array([AGENT_PARAMS[n].v0 for n in TYPE_NAMES])
MASS = np.array([AGENT_PARAMS[n].mass for n in TYPE_NAMES])
RADIUS = np.array([AGENT_PARAMS[n].radius for n in TYPE_NAMES])
FALL_RISK = np.array([AGENT_PARAMS[n].fall_risk for n in TYPE_NAMES])


@dataclass
class MemberSpec:
    type_name: str
    is_guardian: bool


# Party templates: (probability weight, [member specs]). A "party" is one arriving
# unit that shares a group_id; the guardian is responsible for the dependents.
_PARTY_TEMPLATES: list[tuple[float, list[MemberSpec]]] = [
    (0.30, [MemberSpec("adult_normal", True)]),                                              # lone adult
    (0.22, [MemberSpec("adult_normal", True), MemberSpec("child", False)]),                  # parent + child
    (0.14, [MemberSpec("adult_normal", True), MemberSpec("child", False), MemberSpec("child", False)]),  # parent + 2 kids
    (0.12, [MemberSpec("elderly", True), MemberSpec("elderly", False)]),                     # elderly couple
    (0.10, [MemberSpec("adult_normal", True), MemberSpec("elderly", False)]),                # adult escorting elder
    (0.07, [MemberSpec("adult_normal", True), MemberSpec("elderly", False), MemberSpec("child", False)]),  # 3-gen family
    (0.05, [MemberSpec("mobility_impaired", True)]),                                         # lone mobility-impaired
]

_WEIGHTS = np.array([w for w, _ in _PARTY_TEMPLATES])
_WEIGHTS = _WEIGHTS / _WEIGHTS.sum()


def generate_party(rng: np.random.Generator, group_id: int) -> list[dict]:
    """Sample one arriving party as a list of agent spec dicts.

    A solo party gets ``group_id = -1`` (no bond); multi-member parties share the
    given ``group_id`` and have exactly one guardian.
    """
    idx = rng.choice(len(_PARTY_TEMPLATES), p=_WEIGHTS)
    members = _PARTY_TEMPLATES[idx][1]
    solo = len(members) == 1
    out = []
    for m in members:
        out.append(
            {
                "type_id": TYPE_IDS[m.type_name],
                "group_id": -1 if solo else group_id,
                "is_guardian": m.is_guardian,
            }
        )
    return out
