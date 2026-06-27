# AGENTS.md — Project Setu

> **Setu** (सेतु, "bridge") — an admin-first crowd-safety and reunification command platform
> for the **Nashik–Trimbakeshwar Simhastha Kumbh Mela 2027**.
>
> This file is the canonical objective brief for *any* coding agent (Claude Code, Cursor,
> Copilot, etc.) working in this repo. `CLAUDE.md` holds Claude-specific working rules and
> points back here for the "what" and "why". `plan.md` holds the technical/simulation design.

---

## 1. The problem we are solving

Over **80 million pilgrims** attend the Simhastha Kumbh Mela. At that scale:

- **Thousands go missing every day** — mostly elderly, rural, multilingual pilgrims separated
  from family in dense crowds.
- The current lost-and-found system is **manual, per-center, and not cross-searched**: a person
  found and logged at Center A is invisible to a family searching at Center B.
- Separations and danger **cluster predictably** at chokepoints, transfer nodes, and ghats —
  especially during **Amrit Snan (royal bath) days**, when case volume spikes **4–5×**.
- The at-risk group often **has no smartphone** and **cannot self-report**. Networks also
  **collapse at peak density** near the ghats.

**The real failure is operational, not technological.** So Setu does not ask pilgrims to install
an app or register themselves. It puts authorities in control.

## 2. Our thesis / the pivot

Most teams will build a pilgrim-facing "report a missing person" app. We are deliberately
**not** doing that. Two convictions drive the design:

1. **Admin-first, not user-first.** The people who can act — police, control room, lost-and-found
   (Kho-Ya-Paya) operators — are the primary (and only required) users. A family that comes to a
   help desk is *served by an operator*, who registers and searches on their behalf. No pilgrim
   smartphone is ever assumed.

2. **Simulate before you deploy.** Before the mela, we **behaviorally simulate** crowd flow,
   surge, congestion, and stampede/panic scenarios over the *real* Nashik geography. The
   simulation tells us **where separations and danger will concentrate**, and we use that to
   **plan force deployment, help-desk placement, and response routing** — instead of reacting
   blind on the day.

> One sentence: **Setu simulates the crowd to plan the response, and gives the control room one
> unified console to register, match, and dispatch — without ever depending on the pilgrim.**

## 3. What we are building (three pillars)

### Pillar A — Behavioral Crowd Simulation (the "physics")
An agent-based / continuum crowd model over the real grounds that reproduces:
- **Baseline flow** of pilgrims between ghats, parking, and transfer nodes.
- **Amrit Snan surge** (4–5× density spike on bath days).
- **Bottleneck congestion** and clogging at the 26 traffic chokepoints / 11 transfer nodes.
- **Panic / stampede propagation** from a trigger at a high-density node.
- **Separation events** — where the density gradient + chokepoint pressure makes families split.
- **Evacuation** dynamics under an emergency.

Outputs: density heatmaps over time, chokepoint pressure curves, predicted **separation hotspots**,
and predicted **stampede-risk** zones. (Full model & tooling in `plan.md`.)

### Pillar B — Deployment & Response Planning
Turn simulation output into actionable plans:
- **Pre-positioning**: how many forces at which of the 14 police stations / zones, per scenario
  (normal vs snan day), via coverage/facility-location optimization.
- **Help-desk (Kho-Ya-Paya) placement** at predicted separation hotspots.
- **Response routing**: nearest-unit dispatch and evacuation paths over the road/path network.

### Pillar C — Admin Command Console (C2) + Unified Registry
The operator-facing application that:
- Lets an operator **register a missing/found person** when a family or a found pilgrim arrives.
- Provides a **single cross-center registry** with **duplicate detection** and **fuzzy /
  cross-language matching** — this directly closes the Center-A-vs-Center-B gap.
- Shows **live density / risk** (from simulation, or from CCTV-zone occupancy if available) on a map.
- Lets the control room **deploy forces and dispatch units**, and track case → reunification.
- Works **offline-first** (peak-density network collapse is assumed).

## 4. The data we have (`data/data/`)

| File | Contents | Used by |
|---|---|---|
| `Synthetic_Missing_Persons_2500.csv` | 2,500 **synthetic** missing-person cases (fake data). Fields incl. `last_seen_location`, `reporting_center`, `is_duplicate_report` (8%), `status`, `resolution_hours`. ~15% no name, ~20% no mobile. | Registry, matching, hotspot ground-truth |
| `CCTV_Locations.csv` | 1,280 cameras across 32 zones (GPS only, **no footage**). | Coverage map, zone occupancy proxy |
| `Zone_Boundaries.csv` | 32 admin zones (centroids + boundary point counts). | Sim mesh, zone aggregation |
| `Chokepoints_Parking.csv` | 85 real points: 26 traffic chokepoints, 11 transfer nodes, 3 no-vehicle pressure zones, 30 parking, 10 outer parking, 5 belts. | **Sim bottlenecks**, hotspot priors, help-desk siting |
| `Police_Stations.csv` | 14 **real** police stations serving the mela. | Force deployment, dispatch, coverage |

**Geography:** Nashik / Trimbakeshwar, roughly **lat 19.90–20.05, lng 73.71–73.84**.

**Data rules:** all missing-person records are synthetic — *no real personal data exists or should
ever be added*. The CSVs are for **testing the pipeline, not training models from scratch** — use
**pre-trained** models for any ML.

## 5. Design constraints (non-negotiable)

1. **No pilgrim dependency.** Never assume a smartphone, literacy, or a working network on the
   pilgrim side. Every critical path must work via an operator at a desk.
2. **Offline-first.** The console and registry must degrade gracefully and sync later. Networks
   fail at the ghats on snan days.
3. **Privacy by design.** Minimal PII, access-controlled, purpose-limited, deletable. Treat even
   synthetic records as if real.
4. **Multilingual / low-literacy aware.** Names cross scripts and languages; matching must be
   phonetic/fuzzy, not exact-string.
5. **Deployability over cleverness.** Judged on "could this run at scale?" Prefer robust and
   simple to fragile and fancy.

## 6. Success criteria (what "done" looks like)

- [ ] Simulation reproduces a believable **snan-day surge** and a **stampede/panic** scenario over
      the real geography, and emits **density + separation-hotspot + risk** layers.
- [ ] A **deployment plan** (forces + help desks) is generated from sim output and is visibly
      better than naive uniform placement on a coverage metric.
- [ ] Admin console can **register, search, and de-duplicate** cases across centers — demonstrably
      catching the 8% cross-center duplicates in the dataset.
- [ ] Console runs a **dispatch/routing** action from a case to the nearest unit.
- [ ] Core registry + search path works **offline** and **without any pilgrim device**.

## 7. Repo layout (target)

```
.
├── AGENTS.md            # this file — objective for all agents
├── CLAUDE.md            # Claude-specific working rules (points here)
├── plan.md              # simulation/physics + planning + matching tech plan
├── data/data/*.csv      # provided datasets (synthetic / real geo)
├── sim/                 # Pillar A — crowd simulation
├── planning/            # Pillar B — deployment & routing optimization
├── registry/            # Pillar C — matching + unified registry (backend)
├── console/             # Pillar C — admin command UI
└── shared/              # geo utils, data loaders, common schemas
```
*(Directories are created as each pillar is implemented; not all exist yet.)*

## 8. Working agreement for agents

- **Read `plan.md` before touching `sim/` or `planning/`.** It fixes the modeling choices.
- **Ground everything in the real data** — zone IDs, chokepoint categories, police coordinates.
  Don't invent geography.
- **Surface assumptions and tradeoffs** before large changes; prefer the simplest thing that meets
  the success criterion (see global guidelines in `~/.claude/CLAUDE.md`).
- **Never add real PII.** Never commit anything implying a real missing person.
- Keep simulation, planning, registry, and console **decoupled** — they connect through data
  artifacts and a small shared schema, not tangled imports.

---
*Claude Impact Lab — Mumbai 2026 · Kumbh Mela 2027 · in partnership with Kumbhathon Innovation
Foundation & the Government of Maharashtra.*
