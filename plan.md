# SANGAM — Cross-Site Reunification Console for Simhastha Kumbh 2027
### Claude Impact Lab, Mumbai 2026 · 4 members · 5-hour build · FastAPI + React

> **One-line pitch (for the Kumbhathon panel):** SANGAM is the layer that makes your existing
> lost-and-found camps *cross-search each other* — including across the 30 km between Nashik
> (Ramkund) and Trimbakeshwar (Kushavarta). One operator console: register a report → Claude matches
> it against the other site → verify identity before handover → reunite. It works when the network
> doesn't, and it enforces your child-handover SOP so a person is never given to the wrong hands.

**Who we're pitching to.** Kumbhathon administration — the people running the technology for the 2027
Simhastha. They score exactly one question: *"would I pilot this at one camp next year?"* Novelty does
not move them; **operational fit, offline reliability, and respecting their existing process do.** Every
choice below bends to that.

---

## 0. The #1 rule for not failing the merge (unchanged — this part was right)
Each member owns **one backend service folder** + **one frontend page file**. Nobody edits anyone
else's files. Everyone builds against the **frozen contracts** (§4): the Pydantic `Case` model, the
endpoints, and `frontend/src/api.js`. The only shared files are `backend/main.py` and
`frontend/src/App.jsx`, where each member adds **one line** to register their router/route — trivial
conflicts the lead resolves in seconds.

> ⚠️ FastAPI + React costs ~30 min of extra wiring vs all-Python (two servers, CORS, fetch glue).
> That's exactly why the 0:30 contract-freeze and the shared `api.js` are non-negotiable.

---

## 1. What changed from our first draft, and why

Our first version was **four independent features** (face, voice, sim, KG-routing) that merged cleanly
but demoed as **four disconnected tabs sharing a database**. To an administrator that reads as a science
fair, not a deployable operation. Two structural fixes:

1. **One spine, four feeders.** Same 4 owners, same one-folder-each merge discipline — but all four now
   feed a single flow: **report → match across sites → look-out → verify → reunite.** It demos as *one
   operation you could put at a help desk*, not four demos.
2. **We dropped what hurts us with this audience, kept what wins.**
   - ❌ **Aadhaar capture + face-recognition-over-CCTV.** Aadhaar is a liability a government owner has to
     defend (there's already a public Aadhaar-phishing scam warning around 2027 registration); mass face
     recognition needs justification we can't give in 5 minutes; and we don't have footage (the dataset is
     camera *coords only*). **Photo stays only as: a finder photographs a found person, matched against
     open reports** — no Aadhaar, no surveillance framing.
   - ❌ **Physics crowd simulation.** Built in 5 hours it looks naive to people who run real crowd
     management. Replaced by a **separation-hotspot layer derived from the 2,500 real cases** — smaller
     claim, grounded in *their* data.
   - ❌ **"Knowledge-graph" routing.** Buzzword load-bearing; the real need is just "route the look-out to
     the priority zones / nearest post." Folded into the look-out feature.
   - ✅ **Cross-language voice intake** — our strongest accessibility feature, kept and elevated.
   - ✅ **Added the two things that actually win this room:** the **cross-site Person↔Seeker match** (the
     gap no existing camp closes) and **verification-before-handover** (their anti-trafficking SOP).

---

## 2. Problem statement (grounded in the real 2027 event)

- **Dual-site Kumbh.** The Nashik–Trimbakeshwar Simhastha runs across **two sacred sites ~30 km apart** —
  **Ramkund/Panchavati (Nashik)** and **Kushavarta (Trimbakeshwar)** — with crowd peaks on the Amrit Snans
  (2 Aug, 31 Aug, 11–12 Sep 2027). A person separated at one site is routinely found wandering near the
  other (shuttle transfers, processional drift). **No single help desk sees both ends.**
- **The cross-search gap.** Real lost-and-found infra already exists — the 79-year-old Bhule Bhatke
  Shivir, digital Khoya-Paya camps, LED+PA boards, social-media broadcast. The failure isn't *no system*;
  it's that **the camps don't cross-search**, and here they're split across two towns. Result on the
  ground: ~200–300 separations/day, reunification taking **hours to a week**.
- **The users can't self-serve.** Mostly **elderly, rural, multilingual, often phoneless.** No pilgrim app
  — everything is operator-mediated at a desk.
- **Messy data.** 15% missing names, 20% missing phone, 8% cross-center duplicates.
- **Stakes are real.** The 2003 Ramkund stampede killed 39, mostly women, in a narrow ghat approach —
  which is *why* knowing the separation hotspots matters.
- **There's a named owner actively looking for this:** the **NTKMA**, running 2027 as a
  "Technology-Enabled Kumbh" — the successors to the 2015 **Kumbhathon / MIT** program we're pitching into.

---

## 3. The spine + four owners feeding it

```
                         ┌─────────────────────────────────────────────┐
   (1) INTAKE  ───────►  │              MATCH + VERIFY CORE  (4)        │  ◄─── seeker reports
   person/seeker         │  prefilter (opp. type, time, age/gender,    │
   messy free text       │   geo radius OR cross-site widening)        │
        │                │  → Claude ranks ≤N: confidence + rationale  │
   (2) VOICE  ──enrich──►│   + conflicts + ASKS for the missing fact   │──► REUNION
   audio→transcript→EN   │  → VERIFY-before-handover (SOP) blocks the  │     (operator confirms)
        │                │   wrong claimant                            │
   (3) LOOK-OUT  ───────►│                                             │
   hotspot prior +       └─────────────────────────────────────────────┘
   BOLO + priority zones ──────► pushed to police posts / LED+PA
```

| # | Owner | What they build | Backend folder | Frontend page | Feeds the spine by… |
|---|-------|-----------------|----------------|---------------|---------------------|
| 1 | **Intake & capture** | Register a Person (`found`) or Seeker (`missing`) record; Claude structures messy multilingual free text → the `Case` schema (no hallucinated nulls); attach photo/audio. | `backend/services/intake/` | `pages/Intake.jsx` | creating the matchable records |
| 2 | **Voice & cross-language** | Audio → transcribe (faster-whisper) → translate (Claude) → `transcript`/`transcript_en` on the case. Serves the phoneless/non-literate. | `backend/services/voice/` | `pages/VoiceCapture.jsx` | making a record matchable across languages |
| 3 | **Hotspots & look-out (BOLO)** | Static **separation-hotspot layer** from the 2,500 cases + chokepoints/zones; when a Seeker is filed, Claude emits a **multilingual BOLO + ranked priority zones/nearest posts** over that prior; map layer. | `backend/services/lookout/` | `pages/LookOut.jsx` | telling police *where to look* |
| 4 | **Match + verify core (the IP)** | Deterministic prefilter → Claude bipartite **cross-site** ranking (structured: confidence/rationale/conflicts, **abstains + asks for the discriminating fact** on weak evidence) → **verification-before-handover** checklist that gates `Matched → Reunited` and flags claimant mismatches. | `backend/services/match/` | `pages/MatchReview.jsx` | the reunification itself |

> Same merge mechanics as before — four owners, four folders, one-line registration to integrate.
> The difference is they now point at **one operation**, so the demo is a story, not a tour.

---

## 4. Frozen shared contracts (build against these — do NOT change after 0:30)

### 4.1 Canonical `Case` model — `backend/shared/schema.py`
```python
class Case(BaseModel):
    case_id: str                      # "KMP-2027-00001"
    type: str                         # "missing" (=SEEKER) | "found" (=PERSON)  <- the pivot
    site: str | None = None           # "nashik_ramkund" | "trimbak_kushavarta"  <- enables cross-site match
    name: str | None = None           # ~15% blank — never required, never hallucinated
    name_normalized: str = ""         # lowercased + transliterated
    gender: str | None = None
    age_band: str | None = None       # "0-12","13-25",...,"80+"
    language: str | None = None
    state: str | None = None
    district: str | None = None
    last_seen_location: str | None = None
    last_seen_zone: str | None = None # gazetteer-snapped
    lat: float | None = None          # filled by shared/geo.py
    lng: float | None = None
    reporting_center: str | None = None
    reporter_mobile: str | None = None        # ~20% blank
    physical_description: str | None = None
    attributes: dict = {}             # Claude-structured: {attire, marks, build, companions}
    photo_path: str | None = None
    audio_path: str | None = None
    transcript: str | None = None
    transcript_en: str | None = None
    status: str = "Active"            # "Active" | "Matched" | "Verifying" | "Reunited" | "Transferred"
    matched_case_id: str | None = None
    match_confidence: float | None = None
    verification_flags: list[str] = []
    is_duplicate_of: str | None = None
    reported_at: str = ""
    remarks: str | None = None
```

### 4.2 Endpoints (each member owns their router; Member 4 owns the two coupled spine endpoints)
```
POST /api/intake                                   # Member 1
  body (multipart): free_text, type, site, image?, audio_case_id?
  resp: Case                                       # Claude-structured; nulls stay null

POST /api/voice/transcribe                         # Member 2
  body (multipart): audio
  resp: { language, transcript, transcript_en }

POST /api/match                                    # Member 4
  body: { case_id }
  resp: { candidates: [{ case_id, confidence, rationale,
                         conflicting_fields:[], supporting_fields:[] }],
          abstain: bool, ask: str | null }         # ask = the one fact that would resolve it

POST /api/verify                                   # Member 4
  body: { case_id, matched_case_id, claimant: { name, relation, corroborating_fact } }
  resp: { verification_flags: [str], cleared: bool }   # operator alone confirms — never auto

POST /api/lookout                                  # Member 3
  body: { case_id }                                # a SEEKER record
  resp: { brief_by_language: { hi, mr, en, ... },
          priority_zones: [{ zone, lat, lng, risk }],
          nearest_posts: [{ name, lat, lng }] }
```

### 4.3 Frontend shared helper — `frontend/src/api.js` (FROZEN)
```js
const J = (p, body) => fetch(`/api/${p}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(r=>r.json());
const F = (p, form) => fetch(`/api/${p}`, {method:'POST', body:form}).then(r=>r.json());
export const intake     = (form) => F('intake', form);
export const transcribe = (form) => F('voice/transcribe', form);
export const runMatch   = (body) => J('match', body);
export const verify     = (body) => J('verify', body);
export const lookout    = (body) => J('lookout', body);
```

> If you need an input another feature produces, **mock it** with a hard-coded value first. Wire the real
> call only during integration.

---

## 5. Architecture (why it still merges cleanly)
```
        React (Vite) :5173                          FastAPI :8000
   ┌───────────────────────────┐             ┌───────────────────────────┐
   │ App.jsx  (routes/tabs)     │             │ main.py (mounts routers)   │ <- lead owns both
   │ src/pages/                 │  fetch via  │ services/                  │
   │  ├ Intake.jsx     ────────────api.js────▶│  ├ intake/router.py        │ Member 1
   │  ├ VoiceCapture.jsx        │   (proxy)   │  ├ voice/router.py         │ Member 2
   │  ├ LookOut.jsx             │             │  ├ lookout/router.py       │ Member 3
   │  └ MatchReview.jsx         │             │  └ match/router.py         │ Member 4
   │ src/api.js (FROZEN)        │             │ shared/ schema·db·geo·llm  │
   └───────────────────────────┘             │ data/ (5 CSVs, read-only)  │
                                              └───────────────────────────┘
```
- Integration = lead adds 4 `include_router(...)` lines to `main.py` + 4 routes to `App.jsx`.
- **Vite dev proxy** (`/api → :8000`) kills CORS. Fallback: FastAPI `CORSMiddleware`.
- New shared file: `shared/llm.py` — one thin Claude client (Sonnet default, Opus for the hero match)
  with the structured-output helper. **Lead owns it; freeze at 0:30.** Everyone calls it; nobody forks it.

---

## 6. Tech stack (our decision — kept; only the re-centered bits changed)

| Layer | Choice | Note |
|-------|--------|------|
| Frontend | **React + Vite** | Vite proxy kills CORS |
| Map | **react-leaflet** | sites, case pins, hotspot layer, priority zones |
| Backend | **FastAPI + uvicorn** | one app, 4 routers, `/docs` for live endpoint fallback |
| Data | **SQLite + pandas** | seeded from the 5 CSVs |
| Reasoning | **Claude API** (`claude-sonnet-4-6`, `claude-opus-4-8` for hero match) | intake structuring, translation, match+abstain, BOLO, verify flags. **No training.** |
| Voice | **faster-whisper** | CPU-friendly transcription |
| Hotspots | **pandas/numpy** over the 2,500 cases | aggregate `last_seen` → zone risk weights (NOT a physics sim) |
| Look-out routing | **networkx + geopy** | nearest-post / priority-zone ordering; geodesic distance |
| Photo (optional) | attach to record; CLIP-on-description if time | **no Aadhaar, no face-rec-over-CCTV** |

> **Credit is not the bottleneck — time is.** $400 across 4 keys is ~26M tokens each way of Sonnet; you
> can't spend it in 5 hours. Don't tier or cache for cost. Use the best model freely. The only real API
> risk is a flaky call in the live demo → §10.
>
> ⚠️ **Install landmines (kick off in the first 10 min, in parallel):** `faster-whisper`/`onnxruntime`
> and `node_modules` are heavy — start `pip install` and `npm install` immediately. Skip `dlib`/`face_recognition` entirely (we cut face-rec).

---

## 7. Repo layout
```
sangam/
├── backend/
│   ├── main.py                  # mounts routers (lead)
│   ├── shared/                  # FROZEN after 0:30 — lead owns
│   │   ├── schema.py            # Case model
│   │   ├── db.py                # SQLite seeded from CSVs
│   │   ├── geo.py               # last_seen text -> zone/lat/lng + site
│   │   └── llm.py               # Claude client + structured-output helper
│   ├── services/
│   │   ├── intake/              # Member 1
│   │   ├── voice/               # Member 2
│   │   ├── lookout/             # Member 3
│   │   └── match/               # Member 4  (match + verify)
│   ├── data/                    # 5 CSVs (read-only) + photos/ + audio/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # routes (lead)
│   │   ├── api.js               # FROZEN
│   │   └── pages/{Intake,VoiceCapture,LookOut,MatchReview}.jsx
│   ├── vite.config.js           # proxy /api -> :8000
│   └── package.json
└── PLAN.md
```

---

## 8. Git workflow (unchanged — it works)
- `main` protected; never push directly. One branch per member: `feat/intake`, `feat/voice`,
  `feat/lookout`, `feat/match`.
- Touch only your own service folder + your own page file.
- Only shared edits: `main.py` and `App.jsx` — your **one registration line**, committed alone.
- Commit/push every ~30 min. Any `shared/` or `api.js` change → ping the lead; they make it once.

---

## 9. The 5-hour timeline

| Time | Phase | What happens |
|------|-------|--------------|
| **0:00–0:30** | **Setup sprint (ALL)** | Repo + skeleton; kick off `pip`/`npm` installs; **freeze** `schema.py`, the endpoints, `api.js`, and `shared/llm.py`; confirm Vite proxy hits `/api/ping`; **agree the hero scenario** (the cross-site matched pair + the wrong-claimant); split branches. Do not skip. |
| **0:30–3:30** | **Independent build** | Each builds their router + page against the contract, mocking external inputs. **Member 1 seeds the hero records first** so 2/3/4 have real data to build on. Push every 30 min. Aim for a working slice. |
| **3:30–4:00** | **Self-demo checkpoint** | Each page hits its endpoint and shows a result. **Freeze features.** |
| **4:00–4:30** | **Integration (lead + all)** | Mount routers, add routes, seed shared DB, run the **full spine end-to-end** on one map. |
| **4:30–5:00** | **Demo prep** | Rehearse §10 twice; **pre-cache the hero match call**; record a screen-capture fallback; fix only demo-breaking bugs. |

---

## 10. The demo — ONE coherent story (4 min, rehearse it)

Not a tour of tabs. A documented case at a help desk.

1. **The gap (25s):** "Today, a person lost at Trimbakeshwar and found at Nashik — 30 km apart — can sit
   uncatalogued for *days*, because the camps don't cross-search. Mostly elderly, mostly phoneless."
2. **Report comes in (40s):** Operator at **Trimbak/Kushavarta** files a Seeker report for *Kamala-bai*
   in messy Maithili/Hindi → Claude structures it (Intake + Voice) → **LookOut** fires: BOLO in three
   languages + priority zones light up the hotspot map; pushed to the nearest posts. *"Your police now
   know where to look."*
3. **The match (60s):** 30 km away at **Nashik/Ramkund**, a wandering elder is registered as a Person →
   **MatchReview** instantly surfaces the Trimbak Seeker at **0.91** with a plain rationale ("green saree
   + ear studs + Maithili + age band; found ~90 min after last-seen, consistent with a shuttle transfer").
   *"This cross-site link is the thing nothing today does."*
4. **The block (45s) — the beat that wins this room:** A claimant arrives. Descriptions *almost* line up.
   **Verify** flags the inconsistency and **blocks the handover.** *"This is your existing child-handover
   SOP — photograph the claimant, verify the relation — enforced at scale, catching what a volunteer at
   hour fourteen would miss."*
5. **Reunion (20s):** The real family corroborates → operator confirms → `Reunited`; case auto-anonymized.
6. **Deployable close (30s):** "No new parallel system — this rides on your Khoya-Paya camps, your LED+PA
   boards, your police posts. It works when the network's down. Pilot it at **one camp at Ramkund**, then
   both sites, then all camps." (→ §11 objections; → phased pilot.)

**Two lines that land:** *"hours-to-a-week today → 90 seconds across 30 kilometres,"* and *"when the wrong
person came to claim her, it said no."* Architecture goes in the **last 20 seconds**, never the first.

---

## 11. Objections the Kumbhathon panel WILL raise (have these crisp — this is the real scorecard)

| They'll ask | Our answer |
|---|---|
| **Who operates it?** | Existing help-desk staff/volunteers — same people, same desk. No engineers on site. |
| **On what device?** | A cheap tablet/PC at the camp terminal; the console is the only screen they touch. |
| **Which languages?** | Claude handles intake/translation natively — Marathi, Hindi, English + regional (Maithili, Telugu…). Demoed live. |
| **Who owns the data? Aadhaar?** | Government-owned; **on-prem/VPC option**; **no Aadhaar capture**; only match-necessary fields leave the box; **hard-delete/anonymize on reunion**; audit-logged. |
| **What happens offline?** | Network drops at the ghats on snan days — so the **deterministic prefilter + manual search keep reunifying with the LLM/network down**; matches re-rank when the link returns. *(Hero feature, not a caveat.)* |
| **How does it reach police / the LED+PA boards?** | LookOut emits a structured BOLO + a display feed that **pushes to your existing PA/LED hardware and post terminals** — we integrate, not replace. |
| **Wrong reunion / trafficking?** | **Verify-before-handover** enforces your SOP and flags mismatches; the operator alone confirms; never auto-merge. |

---

## 12. Scope discipline (cut order if you fall behind)
- **Never cut:** Intake (Member 1) + Match/Verify (Member 4). That's the spine and the whole demo.
- **Voice:** 3–4 pre-recorded clips, no live mic. Translation via Claude.
- **Hotspots:** a pandas aggregation over the 2,500 cases beats any sim. Tier-1 = render it; **don't build
  a physics engine.** (A pre-baked surge animation is a *stretch*, gated on the spine being green by H3.)
- **Look-out routing:** networkx geodesic nearest-post is enough; skip real road data.
- **Photo:** optional attach; cut entirely before cutting anything on the spine.
- If wiring runs late: each page can fall back to FastAPI `/docs` "Try it out" to prove the endpoint live.
- **A working narrow demo of the spine beats a broad broken one.**

---

## 13. Claude usage + live-demo robustness
- **Claude does the reasoning, we train nothing:** intake structuring, transliteration/translation, the
  cross-site match (with abstain/ask), the BOLO, the verification flags. All via `shared/llm.py` with
  structured outputs (`tools` / `strict`) so we never parse free text.
- **Pre-cache the hero match + verify calls** and serve the cached response in the demo (visible "live"
  toggle). A 3-second hiccup must never kill the moment.
- Keep a **recorded screen capture** as the ultimate fallback, and **one backup API key** in case a
  dry-run trips a rate limit.

---

## 14. First commands
```bash
# --- backend ---
cd backend && python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python shared/db.py                 # seed SQLite from CSVs (one-time)
uvicorn main:app --reload --port 8000

# --- frontend (new terminal) ---
cd frontend && npm install
npm run dev                         # Vite :5173, proxies /api -> :8000
```
