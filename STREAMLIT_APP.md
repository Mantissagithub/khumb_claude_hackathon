# KumbhSeva — Unified Streamlit App

One Streamlit front-end over the **whole** combined backend (the merge of the
`ashutosh`, `env-sim`, and `manan` branches). It replaces juggling the React SPA +
FastAPI + WebGPU console with a single runnable app that imports the backend logic
directly — no separate API server required.

## Run

```bash
pip install -r requirements.txt        # or: ./venv/bin/pip install -r requirements.txt
streamlit run streamlit_app.py         # or: ./run_streamlit.sh
# open http://localhost:8501
```

First boot auto-creates and seeds the SQLite registry (`backend/data/sangam.db`,
2500 cases) from `data/data/Synthetic_Missing_Persons_2500.csv`.

## What's inside

Use the **Role** selector in the sidebar (Public / Operator / Admin) to unlock surfaces.

| Page | Role | What it does |
|------|------|--------------|
| 📊 Dashboard | all | Registry KPIs, status & zone breakdowns, layered ops map (cases / CCTV / police / chokepoints) |
| 📝 Report a person | all | Public submission form (+ optional photo) → enters the review queue |
| 🔍 Search & Match | all | Ranked candidates from the active registry (candidate-blocked + cached) |
| 🗂️ Review queue | Operator/Admin | Triage submissions: find matches, confirm, promote to a new case, reject, mark reunited |
| 🧑‍🤝‍🧑 Crowd simulation | Operator/Admin | Social-Force crowd sim over the Ramkund ghat corridor; pressure/separation hotspots |
| 🚓 Deployment planning | Operator/Admin | sim → Claude/heuristic plan → re-sim → scorecard vs naive-uniform |

For live Claude planning set `ANTHROPIC_API_KEY`; otherwise the planner uses the
local heuristic (fully runnable). Face/voice matching (torch/faiss) is **not**
required — the app degrades gracefully without it.

## Architecture

```
streamlit_app.py            # entry: role-gated st.navigation
app_ui/
  lib/
    bootstrap.py            # sys.path + DB seed (idempotent)
    data.py                 # direct SQLite registry layer (cached reads, cache-busting writes)
    matching.py             # fast cached matcher: precomputed token index + candidate blocking
    simwrap.py              # cached wrappers over sim/ and planning/
  pages/                    # one render() per page
```

The app owns the repo-root `shared` package (sim/planning contracts) and talks to
the seeded SQLite DB directly, sidestepping the `shared` vs `backend/shared`
package-name collision.

## Performance choices

- `@st.cache_data` on every registry/CSV read; writes call a targeted cache-bust.
- `@st.cache_resource` match index: each Active case is tokenised **once**, not
  re-tokenised per query (the slow path flagged in the codebase audit).
- Candidate **blocking** (gender / age band / zone) before scoring, so a query
  touches a small candidate set instead of a full-pool scan.
- Memoised geo resolution (`lru_cache`) and SQL indexes on `status` / `zone` /
  `(gender, age_band)`.
- `@st.cache_data` on simulation + planning runs so re-rendering never re-simulates.
