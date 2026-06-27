"""The closed loop: situation report -> plan -> apply -> re-sim -> scorecard.

Run:  python -m planning.plan_bridge --scenario snan_surge --planner auto

``--planner auto`` calls Claude when a key is configured and otherwise falls back
to the local heuristic planner so the loop is always runnable. Either way the
plan is scored against a naive-uniform plan of equal budget, and the scorecard
reports whether the plan wins on the composite metric (AGENTS.md §6).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shared.schema import DeploymentPlan, Scorecard, SituationReport
from sim.geometry import RAMKUND, Corridor
from sim.scenarios import run_scenario

from .naive import heuristic_plan, naive_uniform_plan
from .scoring import composite, score_deployment

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def _get_plan(planner: str, report: SituationReport, corridor: Corridor) -> tuple[DeploymentPlan, str]:
    if planner in ("auto", "claude"):
        try:
            from .llm import claude_plan
            return claude_plan(report), "claude"
        except Exception as e:  # missing key, network, etc.
            if planner == "claude":
                raise
            print(f"  [planner] Claude unavailable ({type(e).__name__}: {e}); using heuristic fallback.")
    return heuristic_plan(report, corridor), "heuristic"


def run_bridge(scenario: str, planner: str, seed: int, report_path: str | None) -> Scorecard:
    corridor = Corridor(RAMKUND)

    # No-control baseline: provides the prediction (situation report) + reference
    # metrics used to normalise the physics terms of the composite.
    base_sim, base_rec, base_report = run_scenario(scenario, deployment=None, seed=seed)
    if report_path:
        base_report = SituationReport.from_dict(json.loads(Path(report_path).read_text()))
        scenario = base_report.scenario
    refs = {"peak_pressure": base_rec.global_peak_pressure,
            "total_separations": len(base_sim.separations)}

    plan, planner_used = _get_plan(planner, base_report, corridor)
    naive = naive_uniform_plan(base_report, corridor, like=plan)

    m_plan, d_plan = score_deployment(scenario, corridor, base_report, plan, seed=seed)
    m_naive, d_naive = score_deployment(scenario, corridor, base_report, naive, seed=seed)

    comp_plan = composite(m_plan, d_plan, refs)
    comp_naive = composite(m_naive, d_naive, refs)

    return Scorecard(
        baseline=m_naive,
        planned=m_plan,
        composite_baseline=comp_naive,
        composite_planned=comp_plan,
        wins=comp_plan > comp_naive,
        detail={
            "scenario": scenario,
            "planner": planner_used,
            "plan_summary": plan.summary,
            "refs_no_control": refs,
            "plan_coverage": d_plan,
            "naive_coverage": d_naive,
            "plan": json.loads(plan.to_json()),
        },
    )


def _print(sc: Scorecard) -> None:
    d = sc.detail
    print(f"\n=== Setu deployment scorecard — scenario '{d['scenario']}' (planner: {d['planner']}) ===")
    print(f"plan: {d['plan_summary']}\n")
    print(f"{'metric':<22}{'naive uniform':>16}{'plan':>16}")
    print(f"{'force coverage':<22}{d['naive_coverage']['force_coverage']:>16.2f}{d['plan_coverage']['force_coverage']:>16.2f}")
    print(f"{'cctv coverage':<22}{sc.baseline.cctv_coverage:>16.2f}{sc.planned.cctv_coverage:>16.2f}")
    print(f"{'helpdesk coverage':<22}{d['naive_coverage']['helpdesk_coverage']:>16.2f}{d['plan_coverage']['helpdesk_coverage']:>16.2f}")
    print(f"{'peak pressure':<22}{sc.baseline.peak_pressure:>16.2f}{sc.planned.peak_pressure:>16.2f}")
    print(f"{'separations':<22}{sc.baseline.total_separations:>16d}{sc.planned.total_separations:>16d}")
    print(f"{'composite':<22}{sc.composite_baseline:>16.3f}{sc.composite_planned:>16.3f}")
    verdict = "PLAN WINS" if sc.wins else "no improvement"
    print(f"\n  => {verdict}  (composite {sc.composite_planned:.3f} vs {sc.composite_baseline:.3f})")


def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(description="Setu sim->Claude->plan->re-sim closed loop")
    ap.add_argument("--scenario", default="snan_surge")
    ap.add_argument("--planner", choices=["auto", "claude", "heuristic"], default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", default=None, help="optional precomputed situation-report JSON")
    ap.add_argument("--out", default=str(ARTIFACTS / "plan"))
    args = ap.parse_args(argv)

    sc = run_bridge(args.scenario, args.planner, args.seed, args.report)
    _print(sc)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.scenario}_scorecard.json").write_text(sc.to_json())
    print(f"\n  wrote {out / (args.scenario + '_scorecard.json')}")


if __name__ == "__main__":
    main(sys.argv[1:])
