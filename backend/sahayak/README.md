# Sahayak (सहायक) — Reunification Web App

A role-based web app served by the FastAPI backend, with **real-time
cross-center match alerts over WebSocket**. Volunteers register found/missing
people; the backend auto-matches by face across all centers; an admin confirms.

## Run
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r ../face_retrieval/requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000     # 0.0.0.0 = reachable on the LAN
```
Open **http://localhost:8000/** → choose **Volunteer** or **Admin**.
On the venue Wi-Fi, others open `http://<this-machine-ip>:8000/`.

## How it works
1. **Volunteer** picks a center, registers a *found* person (or *missing* report)
   with a photo → backend embeds the face (ArcFace/FaceNet) and stores the case.
2. Backend **auto-searches the opposite type across all centers** (cosine) and
   raises **match candidates** with a confidence band.
3. **WebSocket** instantly pushes the candidate to the **Admin** control room and
   to the **centers** involved.
4. **Admin** reviews side-by-side photos + confidence + verdict → **Confirm** or
   **Reject** (human-in-the-loop). On confirm, both cases flip to *Reunited* live
   everywhere.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/centers` · `/api/stats` | preset centers · live counts |
| POST | `/api/cases/register` | multipart: type, center, photo, … → case + candidates |
| GET | `/api/cases` · `/api/cases/{id}/photo` | list · photo |
| GET | `/api/candidates` | pending matches (with both case summaries) |
| POST | `/api/candidates/{id}/{confirm\|reject}` | resolve a match |
| WS | `/ws?role=admin` or `/ws?center=<id>` | realtime events |

WebSocket events: `case.created`, `match.candidate`, `match.resolved`, `status.changed`.

## Notes
- In-memory store (resets on restart) — swap for SQLite without touching the API.
- UI uses Tailwind + Leaflet via CDN (needs internet to load those assets);
  for true offline at the venue, vendor those two files locally.
- Decision-support only: every match is confirmed by a human.
