# 🕉️ KumbhSeva — AI Issue Routing

When a devotee at the Kumbh Mela reports a problem (lost person, medical
emergency, theft, fire, overcrowding…), the description is sent to **Claude**,
which instantly returns a structured suggestion — **which department** should
handle it, **how urgent** it is, **why**, and the **recommended first action**.
The admin control room sees the ticket with this AI suggestion and assigns it to
the right department with **one click** — no time wasted investigating.

## Features

- **AI routing** — Claude (`claude-opus-4-8`) classifies each issue into a
  department + priority + reasoning + recommended action, using **structured
  outputs** so the result is always clean, validated JSON.
- **Native translation** — pilgrims can report in Marathi, Telugu, Maithili,
  Hindi, etc.; Claude translates the summary to **English** for the admin and
  tags the original language. Breaks the language barrier for the control room.
- **Knowledge-graph asset linking** — nearby on-ground assets (hospitals, police
  tents, Lost & Found booths) are fed to Claude so its recommended action names
  the **nearest relevant asset**. (Seed for the full chokepoint-routing graph.)
- **Dispatch roadmap** — once a responder is assigned, each ticket advances
  through **Reported → Dispatched → En route → On-site → Resolved**, tracked on
  the ticket and drivable over the API.
- **Two-engine routing** — uses Claude when a key is set, otherwise a keyword
  heuristic, so the full pipeline runs with **zero setup** for demos. `/health`
  reports which engine and storage backend are live.
- **Pluggable storage** — a local JSON ledger by default, or a live Supabase
  `tickets` table when credentials are present (same record shape for both).

> Duplicate detection / auto-merge exists as a prototype in `legacy/` and is not
> wired into the current API.

## Quick start

```bash
cd ~/KumbhSeva
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp config/secrets.toml.example config/secrets.toml   # add your ANTHROPIC_API_KEY (optional)

uvicorn app.main:app --reload
```

Then:

- API docs (try every endpoint) → http://localhost:8000/docs
- Health / engine status → http://localhost:8000/health

The frontend template consumes the JSON API under `/api/v1`. The Streamlit admin
(`streamlit run streamlit_app.py`) is a reference UI over the same services.

## API

Run it: `uvicorn app.main:app --reload` → docs at http://localhost:8000/docs

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Status + which AI engine / storage backend is live |
| POST | `/api/v1/issues` | Raise an issue → runs Claude triage → stores ticket |
| GET | `/api/v1/issues` | List tickets (dashboard feed; `?status=`, `?department=`) |
| GET | `/api/v1/issues/{id}` | One ticket |
| POST | `/api/v1/issues/{id}/assign` | Admin assigns to a responder (`{department}`) |
| POST | `/api/v1/issues/{id}/dispatch` | Advance the dispatch roadmap (`{stage}` 0–4) |
| GET | `/api/v1/issues/{id}/responder-centres` | Nearest centre for each responder |
| POST | `/api/v1/triage` | Preview AI routing for a description (no ticket saved) |
| GET | `/api/v1/departments` | Responder catalog (Police / Medical / Fire) |
| GET | `/api/v1/assets` | On-ground assets (`?zone=` to filter) |
| GET | `/api/v1/assets/nearest` | Nearest centre for `?department=&latitude=&longitude=&zone=` |

The three responders are **Police**, **Medical**, and **Fire Brigade**. Reports
in any language are translated to English (original language tagged); the ticket
carries the AI department suggestion, priority, reasoning, recommended action,
and the nearest responder centre. Without a Claude key the API still runs via a
keyword fallback. CORS is open by default for local dev — set
`KUMBHSEVA_CORS_ORIGINS` (comma-separated) to restrict it in production.

## Project layout

```
app/
  main.py                  FastAPI app (CORS + /health + mounts /api/v1)
  api/
    routes.py              all endpoints (issues, triage, departments, assets)
    schemas.py             request/response Pydantic models
    deps.py                settings + store dependency (cached)
  services/                portable business logic (shared with the Streamlit admin)
    triage.py              Claude routing + translation (+ keyword fallback)
    store.py               ticket store — LocalStore (JSON) or SupabaseStore
    knowledge_graph.py     on-ground assets / nearest responder centre
config/
  __init__.py              load_secrets() reads config/secrets.toml
  secrets.toml             Claude + Supabase keys (gitignored)
streamlit_app.py           reference admin control-room UI (Streamlit)
data/
  streamlit_ledger.json    local ticket ledger (LocalStore fallback)
legacy/                    earlier 8-department FastAPI prototype (reference only)
```

Both the API and the Streamlit admin call the same `app/services/*`, so they
stay in sync. Keys live in `config/secrets.toml` (copy from
`config/secrets.toml.example`) — no key inputs in any UI.

## Next step: chokepoint-avoiding routes

`knowledge_graph.py` is the seed. The plan is to grow it into a real graph
(zones + CCTV + police + chokepoints as nodes/edges) and add a shortest-path
planner that routes responders **around** congested chokepoints.
