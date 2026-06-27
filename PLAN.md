# SANGAM — Kumbh Mela Reunification & Operations Platform
### Claude Impact Lab, Mumbai 2026 · 4 members · 5-hour build · **FastAPI + React**

> **One-line pitch:** A multimodal system that reunites missing pilgrims across centers using
> face/clothing search + cross-language voice matching, and helps authorities act using
> crowd simulation + knowledge-graph routing — built so 4 people can work independently and
> merge cleanly in the final hour.

---

## 0. The #1 rule for not failing the merge
Each member owns **one backend service folder** + **one frontend page file**. Nobody edits anyone
else's files. Everyone builds against the **frozen contracts** (Section 4): the Pydantic `Case`
model, the 4 REST endpoints, and the shared `frontend/src/api.js`. The only shared files are
`backend/main.py` and `frontend/src/App.jsx`, where each member adds **one line** to register their
router/route — tiny, predictable conflicts the lead resolves in seconds.

> ⚠️ **FastAPI + React costs you ~30 min of extra wiring vs an all-Python app** (two servers, CORS,
> fetch glue). Worth it for the better UI — but that's exactly why the 0:30 contract-freeze and the
> shared `api.js` are non-negotiable.

---

## 1. Problem statement (the brief)
- Kumbh Mela: 80M+ pilgrims; thousands separated daily, mostly **elderly**.
- Core gap: **no cross-search between centers** — a person found at Center A is invisible to a
  family searching at Center B.
- Data is **messy**: 15% missing names, 20% missing phone, 8% cross-center duplicates.
- Must serve **non-literate / phoneless** users and work under **poor connectivity**.

## 2. Our four features (one owner each)

| # | Feature | Owner | Backend folder | Frontend page |
|---|---------|-------|----------------|---------------|
| 1 | **Face + clothing CCTV search.** Volunteer uploads Aadhaar + supporting photos → match against camera gallery → if found, route to that camera/police station. | Member 1 | `backend/services/face_search/` | `frontend/src/pages/FaceSearch.jsx` |
| 2 | **Cross-language voice matching.** Person who can't speak the local language records audio → transcribe + translate → match against records → store audio + transcript on the case. | Member 2 | `backend/services/voice_lang/` | `frontend/src/pages/VoiceMatch.jsx` |
| 3 | **Operations simulation.** Simulate crowd/separation scenarios from the 2,500 cases + chokepoints/zones → predict hotspots & resource needs → plan operations. | Member 3 | `backend/services/simulation/` | `frontend/src/pages/Simulation.jsx` |
| 4 | **Knowledge-graph routing.** Build a KG over cases/zones/CCTV/police/chokepoints → answer department queries with the best route (avoiding chokepoints). | Member 4 | `backend/services/routing_kg/` | `frontend/src/pages/Routing.jsx` |

## 3. Architecture (why this merges cleanly)

```
        React (Vite) :5173                          FastAPI :8000
   ┌───────────────────────────┐             ┌───────────────────────────┐
   │ App.jsx  (routes/tabs)     │             │ main.py (mounts routers)   │ <- lead owns both
   │ src/pages/                 │  fetch via  │ services/                  │
   │  ├ FaceSearch.jsx  ───────────api.js────▶│  ├ face_search/router.py   │ Member 1
   │  ├ VoiceMatch.jsx          │   (CORS)    │  ├ voice_lang/router.py    │ Member 2
   │  ├ Simulation.jsx          │             │  ├ simulation/router.py    │ Member 3
   │  └ Routing.jsx             │             │  └ routing_kg/router.py    │ Member 4
   │ src/api.js (FROZEN)        │             │ shared/ schema·db·geo      │
   └───────────────────────────┘             │ data/ (5 CSVs, read-only)  │
                                              └───────────────────────────┘
```

- Each member owns **one router file** (backend) + **one page component** (frontend). No shared logic.
- Integration = lead adds 4 lines to `main.py` (`app.include_router(...)`) and 4 routes to `App.jsx`.
- Use a **Vite dev proxy** so the frontend calls `/api/...` and Vite forwards to `:8000` — avoids
  CORS headaches and hard-coded URLs. (Fallback: enable FastAPI `CORSMiddleware` for `*`.)

## 4. Frozen shared contracts (build against these — do NOT change after 0:30)

### 4.1 Canonical Case model — `backend/shared/schema.py` (Pydantic)
```python
class Case(BaseModel):
    case_id: str                      # "KMP-2027-00001" or "FOUND-0001"
    type: str                         # "missing" | "found"
    name: str | None = None           # may be empty (15% of data)
    name_normalized: str = ""         # lowercased + transliterated for matching
    gender: str | None = None
    age_band: str | None = None       # "0-12","13-25","26-40","41-60","61-70","71-80","80+"
    language: str | None = None
    state: str | None = None
    district: str | None = None
    last_seen_location: str | None = None
    lat: float | None = None          # filled by shared/geo.py
    lng: float | None = None
    zone: str | None = None           # e.g. "Zone Area 12"
    reporting_center: str | None = None
    reporter_mobile: str | None = None
    physical_description: str | None = None
    photo_path: str | None = None     # under data/photos/
    audio_path: str | None = None     # under data/audio/
    transcript: str | None = None
    transcript_en: str | None = None
    face_embedding: list[float] | None = None
    status: str = "Active"            # "Active" | "Reunited" | "Matched"
    reported_at: str = ""
    remarks: str | None = None
```

### 4.2 The 4 REST endpoints (each member owns one router)
```
POST /api/face/search
  body: multipart file `image` (+ optional `aadhaar`)
  resp: { matches: [{ case_id, score, camera_id, lat, lng, matched_name }],
          route: { to, lat, lng, steps:[str] } | null }

POST /api/voice/match
  body: multipart file `audio`
  resp: { language, transcript, transcript_en,
          candidates: [{ case_id, score, name }] }

POST /api/sim/run
  body: { pilgrims:int, hours:int, seed:int }
  resp: { hotspots: [{ zone, lat, lng, risk }], timeline: [...], resources: {...} }

POST /api/routing/best
  body: { from:str, to:str, avoid_chokepoints:bool }
  resp: { path: [{ name, lat, lng }], distance_km:float, steps:[str] }
```

### 4.3 Frontend shared helper — `frontend/src/api.js` (FROZEN)
```js
const J  = (p, body)   => fetch(`/api/${p}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(r=>r.json());
const F  = (p, form)   => fetch(`/api/${p}`, {method:'POST', body:form}).then(r=>r.json());
export const faceSearch  = (form)  => F('face/search', form);
export const voiceMatch  = (form)  => F('voice/match', form);
export const runSim      = (body)  => J('sim/run', body);
export const bestRoute   = (body)  => J('routing/best', body);
```

> If you need an input another feature produces, **mock it** with a hard-coded value first. Wire the
> real call only during integration.

## 5. Tech stack (chosen for speed + Windows reliability)

| Layer | Choice | Why / install note |
|-------|--------|--------------------|
| Frontend | **React + Vite** | Fast dev server, simple routing, Vite proxy kills CORS |
| Map | **react-leaflet** or **deck.gl** | Plot cases/CCTV/police/routes |
| Backend | **FastAPI** + **uvicorn** | One app, 4 routers; auto OpenAPI docs at `/docs` |
| Data | **SQLite** + **pandas** | Zero setup; seeded from CSVs |
| Face | **InsightFace** + `onnxruntime` | More reliable on Windows than dlib/face_recognition |
| Clothing | **open_clip** / CLIP | Match `physical_description` text ↔ image |
| Voice | **faster-whisper** | Lighter/faster than openai-whisper on CPU |
| Translate | Claude API (or `deep-translator`) | Cross-language name/attribute matching |
| Simulation | **simpy** or numpy Monte Carlo | Agent/stochastic crowd model |
| Routing/KG | **networkx** + **geopy** | Graph + geodesic distances; OSRM = stretch |

> ⚠️ **Install landmines (do in first 30 min, in parallel):** `dlib` is painful on Windows — use
> InsightFace. Heavy wheels (torch/onnxruntime, node_modules) take minutes — start `pip install` and
> `npm install` immediately so they finish while you read this doc.

## 6. Repo layout
```
sangam/
├── backend/
│   ├── main.py                  # FastAPI app, mounts routers (integration lead)
│   ├── shared/                  # FROZEN after 0:30 — owned by lead
│   │   ├── schema.py            # Pydantic Case model
│   │   ├── db.py                # SQLite seeded from CSVs
│   │   └── geo.py               # last_seen_location text -> lat/lng/zone
│   ├── services/
│   │   ├── face_search/         # Member 1  (router.py + logic.py)
│   │   ├── voice_lang/          # Member 2
│   │   ├── simulation/          # Member 3
│   │   └── routing_kg/          # Member 4
│   ├── data/                    # 5 CSVs (read-only) + photos/ + audio/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # routes/tabs (integration lead)
│   │   ├── api.js               # FROZEN shared fetch helpers
│   │   └── pages/
│   │       ├── FaceSearch.jsx   # Member 1
│   │       ├── VoiceMatch.jsx   # Member 2
│   │       ├── Simulation.jsx   # Member 3
│   │       └── Routing.jsx      # Member 4
│   ├── vite.config.js           # proxy /api -> http://localhost:8000
│   └── package.json
├── README.md
└── PLAN.md                      # this file
```

## 7. Git workflow (prevents conflicts)
- `main` is protected — **never push directly to main**.
- One branch per member: `feat/face`, `feat/voice`, `feat/sim`, `feat/routing`.
- **You only touch your own router folder + your own page file.** That's the contract.
- The only shared edit points are `backend/main.py` and `frontend/src/App.jsx` — add your **one
  registration line** and commit it alone, so conflicts are trivial.
- Commit + push every ~30 min. Pull `main` before integration.
- Any `shared/` or `api.js` change → ask the integration lead in chat; they make it once, everyone pulls.

## 8. The 5-hour timeline

| Time | Phase | Everyone |
|------|-------|----------|
| **0:00–0:30** | **Setup sprint (ALL together)** | Create repo + skeleton, run `pip install` & `npm install`, **freeze** `schema.py` + the 4 endpoints + `api.js`, confirm the Vite proxy works (frontend can hit a `/api/ping`), split into branches. **Do not skip this.** |
| **0:30–3:30** | **Independent build** | Each builds backend router + frontend page against the contract, mocking external inputs. Push every 30 min. Target a *working slice*, not perfection. |
| **3:30–4:00** | **Self-demo checkpoint** | Each member's page hits their endpoint and shows a result with sample data. Freeze features now. |
| **4:00–4:30** | **Integration (lead + all)** | Mount 4 routers in `main.py`, add 4 routes in `App.jsx`, seed shared DB, run frontend+backend end-to-end on the global map. |
| **4:30–5:00** | **Demo prep** | Rehearse the 4-minute demo script (below), fix only demo-breaking bugs, prep pitch + README. |

## 9. Demo script (4 minutes — rehearse this)
1. **Hook (20s):** "Thousands of elderly go missing daily at Kumbh, invisible across centers. Sangam fixes that."
2. **Face search (45s):** Upload an Aadhaar + photo → match found on a CCTV camera → "route to nearest police station."
3. **Voice match (45s):** Play an audio clip in a language the volunteer doesn't speak → live transcribe + translate → matched to a missing report.
4. **Simulation (45s):** Run the sim → heatmap shows separation hotspots at chokepoints → "pre-position staff here."
5. **Routing (45s):** Department query → KG returns best route avoiding chokepoints on the map.
6. **Close (20s):** "Offline-capable, works with incomplete data, accessible by voice — deployable across all centers."

## 10. Scope discipline (what to cut if you're behind)
- Face: a small image **gallery folder** stands in for live CCTV. Matching a photo to the gallery is enough.
- Voice: 3–4 pre-recorded clips is enough; no live mic needed.
- Simulation: a stochastic Monte Carlo over zones beats a fancy physics engine you can't finish.
- Routing: networkx geodesic shortest-path is enough; skip real road data (OSRM).
- If wiring runs late: each page can call the FastAPI `/docs` "Try it out" to prove the endpoint works live.
- **A working narrow demo always beats a broken ambitious one.**

## 11. First commands
```bash
# --- backend ---
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python shared/db.py               # seed SQLite from CSVs (one-time)
uvicorn main:app --reload --port 8000

# --- frontend (new terminal) ---
cd frontend
npm install
npm run dev                       # Vite on :5173, proxies /api -> :8000
```
