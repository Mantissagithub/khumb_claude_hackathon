# CLAUDE.md — Project Setu (Claude Code working rules)

Project-specific guidance for Claude Code in this repo. This **complements** the global rules in
`~/.claude/CLAUDE.md` (Think Before Coding · Simplicity First · Surgical Changes · Goal-Driven).
For the full objective, the pivot, and architecture, read **`AGENTS.md`**. For the simulation and
modeling tech, read **`plan.md`**. Don't duplicate those here — point to them.

## What this project is (one paragraph)

Setu is an **admin-first** crowd-safety + reunification command platform for the **Nashik–
Trimbakeshwar Kumbh Mela 2027**. We **behaviorally simulate** crowd flow / surge / stampede over the
*real* Nashik geography to **plan police and crowd-control deployment**, and give the control room a
**single console** to register, cross-match, and dispatch — **without ever depending on a pilgrim's
phone**. Three pillars: **A) simulation**, **B) deployment planning**, **C) admin console +
unified registry**.

## Non-negotiables (read before writing code)

1. **No pilgrim-side dependency.** Never assume a smartphone, literacy, or network on the pilgrim
   side. Every critical path runs through an operator at a desk.
2. **Offline-first.** Registry + search must degrade and sync; networks collapse at the ghats.
3. **No real PII, ever.** All missing-person data is synthetic. Never add, infer, or commit data
   implying a real person.
4. **Pre-trained models only** for ML — the data is for testing the pipeline, not training.
5. **Ground in real data.** Use the actual zones / chokepoints / police coordinates in
   `data/data/`. Don't invent geography. Nashik bounds ≈ lat 19.90–20.05, lng 73.71–73.84.

## How to work here

- **Plan first, then code.** State assumptions and tradeoffs; if multiple interpretations exist,
  ask (don't silently pick). Keep changes surgical and scoped to the request.
- **Keep the four pillars decoupled** — `sim/`, `planning/`, `registry/`, `console/` connect via
  data artifacts + a small shared schema in `shared/`, not tangled imports.
- **Define a verifiable success check per task** (see `AGENTS.md §6`) and loop until it passes.
- When a task touches simulation or planning, **re-read `plan.md` first** so modeling choices stay
  consistent.

## Conventions

- **Language:** Python for `sim/`, `planning/`, `registry/` (geo + ML ecosystem). Console stack is
  TBD (see `plan.md`); keep backend API-first so the UI choice stays swappable.
- **Geo:** lon/lat order matters — store as `(lng, lat)` to match the CSVs; be explicit in code.
- **Data loading:** go through `shared/` loaders; don't re-parse CSVs ad hoc in each module.
- **Secrets / config:** never hardcode; no credentials in the repo.

## Commands

> Pillar A (simulation) and Pillar B (planning bridge) are implemented in pure Python. No build
> tooling yet; install dependencies manually. No automated test suite; each module was verified
> via inline checks. `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) is needed for the live
> Claude planner; the loop falls back to a built-in heuristic planner when the key is absent.

```bash
# setup — install dependencies (already present in this environment; listed for reproducibility)
pip install numpy numba scikit-fmm anthropic

# run sim — execute a scenario; writes situation report + density CSV to artifacts/<scenario>/
python -m sim.scenarios <baseline|snan_surge|stampede|evacuation>

# run planning loop — sim → Claude → plan → re-sim → scorecard vs naive uniform deployment
python -m planning.plan_bridge --scenario snan_surge --planner auto
#   --planner auto       use Claude if ANTHROPIC_API_KEY is set, else fall back to heuristic
#   --planner heuristic  force the keyless built-in planner
#   --planner claude     require the live Claude call (fails without a key)

# tests — no automated suite yet
```

## Status

Bootstrapping. Only datasets (`data/data/`) and these planning docs exist so far. Build order
follows `plan.md`: simulation core → planning layer → registry/matching → console.
