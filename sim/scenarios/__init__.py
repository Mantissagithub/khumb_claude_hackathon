"""Scenario definitions and the scenario runner.

Four scenarios over the Ramkund corridor (AGENTS.md §3):
    baseline    steady free-flow pilgrim arrivals
    snan_surge  4-5x Amrit-Snan density spike then relax
    stampede    a surge plus a panic trigger (faster-is-slower crush)
    evacuation  goal flips from the ghat to the top exit; measure egress

Run one with ``python -m sim.scenarios <name>`` or import :func:`run_scenario`.
"""

from .run import SCENARIOS, ScenarioSpec, run_scenario

__all__ = ["SCENARIOS", "ScenarioSpec", "run_scenario"]
