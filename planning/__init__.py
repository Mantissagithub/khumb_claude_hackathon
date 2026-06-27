"""Pillar B — turn simulation output into a deployment plan, via Claude.

Closed loop: sim situation report -> Claude (structured DeploymentPlan) -> apply
as controllables -> re-simulate -> score against a naive-uniform plan of equal
budget on a coverage-centred composite metric (AGENTS.md §6).
"""

from .llm import claude_plan
from .naive import heuristic_plan, naive_uniform_plan
from .scoring import score_deployment

__all__ = ["claude_plan", "heuristic_plan", "naive_uniform_plan", "score_deployment"]
