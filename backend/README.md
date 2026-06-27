# Sangam Backend — Auth, Public Submission & Admin Review

FastAPI + SQLite. Wraps the 4 feature modules with an identity/trust layer:
public (anonymous) missing-person reports → staff review queue → match → reunite.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

`init_db()` runs on startup: seeds 2500 `cases` from the CSV and the demo staff
accounts (idempotent — safe to re-run). API docs at <http://localhost:8000/docs>.

To reset to a clean demo state: stop the server and `rm data/sangam.db` (it
re-seeds on next start).

## Demo credentials

| Username   | Password      | Role     | Can do                                         |
|------------|---------------|----------|------------------------------------------------|
| `admin`    | `admin123`    | admin    | Everything + manage staff + analytics          |
| `operator` | `operator123` | operator | Review queue, run matches, confirm, reunite    |

## Surfaces

- **Public (no auth):** `POST /api/public/submit` — anyone reports a missing person (photo + details + their phone). Lands in the review queue as `pending`.
- **Auth:** `POST /api/auth/login` (form-encoded), `GET /api/auth/me`.
- **Admin/staff (JWT):** submissions queue, `/match`, confirm / promote / reject, `cases/{id}/reunite`, `cases` browse; staff CRUD + `analytics/summary` are **admin-only**.

## Flow

```
public submit → submissions(pending)
   → operator opens → /match (text + attribute scoring vs cases)
      → confirm(case_id)  → submission=matched,  case=Matched → reunite → case=Reunited
      → promote           → new PUB-xxxxx case (Active)
      → reject            → submission=rejected
```

Matching is currently **text + attribute** based (description term overlap +
gender/age/zone boosts). Face-embedding scoring plugs into `/match` via
`services/face_search/logic.py` when that module is ready (see PLAN.md).
