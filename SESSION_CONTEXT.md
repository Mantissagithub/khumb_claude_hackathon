# Session Context — Sangam (Kumbh Mela Reunification)

> Working session log: research → gap analysis → competitive scan → feature plan → built & verified an auth + public-submission + admin-review layer on the Sangam app.
> Date: 2026-06-27 · Branch: `ashutosh-branch-front-end`

---

## 1. Research — Maha Kumbh 2025 "Lost & Found" system

Source: [HinduPost article](https://hindupost.in/dharma-religion/mahakumbh-2025/ai-technology-powered-high-tech-lost-and-found-registration-centre-established-at-maha-kumbh-mela-to-reunite-people-separated-from-their-families/) + public record (web search was blocked in the env).

**What it is:** The **"Digital Kho-Ya-Paya Kendra"** / Bhula-Bhatka center (helpline **1920**), run by the Mela Authority + UP Police to reunite separated pilgrims.

**Features:** digital registration across centers, AI facial recognition, PA/loudspeaker announcements, LED display screens, helpline 1920, social-media broadcasting, police/CCTV integration, dedicated handling for children/elderly/women.

**Problem:** ~660M attendees (largest human gathering on record); rural/elderly/illiterate crowd; people get separated; manual paper+loudspeaker process doesn't scale; stampede risk (Jan 29 2025 crush killed 30+).

**Solution:** centralized AI-assisted registry that registers → matches → broadcasts → coordinates.

---

## 2. Gaps in the current system

1. **Reactive, not proactive** — only acts after someone reaches a kendra.
2. **Two-sided match problem** — face recognition needs photos on *both* sides; families often lack a photo of the lost person.
3. **Excludes the most at-risk** — app/form/literacy/phone assumptions fail rural elderly & children; networks collapse in crowds.
4. **Vulnerable can't self-register** — lost child / dementia patient / non-verbal.
5. **Fragmented databases** — police vs official kendra vs NGO camps not unified.
6. **No location intelligence** — no last-seen geotag / hotspots.
7. **Weak reunification verification** — trafficking / wrongful-claim risk.

---

## 3. Innovation wedges (for Sangam)

1. 🥇 **Crowdsource the "found" side** — any bystander photographs a lost person → supplies the photo families lack (solves two-sided match).
2. 🥈 **Multilingual AI voice agent** — talks to illiterate/panicked person in their dialect, registers by voice (the real LLM/Claude play); + IVR/SMS/WhatsApp for feature phones.
3. 🥉 **Proactive prevention** — low-cost QR/NFC tags for kids & elderly, scan-to-reunite.
4. Unified index across agencies · last-seen geo + hotspots · verified reunification handshake · unidentifiable-person workflow.

**Recommended hackathon wedge:** anyone registers a lost person in seconds (voice or photo, any language) + AI matches across one unified registry.

---

## 4. Competitive scan

| System | Approach | Key takeaway |
|---|---|---|
| **China** | Permanent national-ID graph + 700M cameras + Skynet/Sharp Eyes facial recognition; Tencent "Reunion" cross-age face matching (reunites children after decades) | Identifying the non-communicative & matching old→current faces is *technically solvable* — but it's non-consensual mass surveillance (not legal/desirable in India under Puttaswamy). |
| **Tomorrowland / festivals** | RFID wristband bound to identity at the gate + app "Find My Friends" + meeting points + child wristband w/ parent phone | Festivals *prevent* the hard problem by binding identity at a ticketed gate. |
| **Hajj** (closest analog) | e-bracelet storing pilgrim data, Nusuk app, 9-language support, elderly lanes | Wearable makes a non-communicative found pilgrim identifiable. |

**Insight:** Festivals win by binding identity *at the gate*. The Kumbh has **no gate** — so Sangam's job is to recreate identity binding *after* separation, *without* a phone/ticket/literacy. That's the uncovered gap.

---

## 5. Feature decision — Auth + Public + Admin layer

User asked to add a **user/login** model (since anyone can submit images) and a **staff admin panel** to review & match.

**Locked decisions:**
1. Public submission = **no login**, just a form (anonymous; submitter gives own contact phone).
2. Staff = **username + password (hashed) + JWT**, role-based.
3. Roles = **operator** (review, match, reunite) + **admin** (+ manage staff + analytics).
4. Scope = **add this layer around** the existing 4 feature modules (also built the missing backend).

Full plan: `~/.claude/plans/zippy-churning-nova.md`.

---

## 6. What was built & verified

### Backend (greenfield FastAPI + SQLite) — `backend/`
- `shared/db.py` — tables `cases` / `staff` / `submissions`; seeds **2500 cases** from `data/data/Synthetic_Missing_Persons_2500.csv` (pandas) + demo staff; idempotent `init_db()`.
- `shared/security.py` — passlib bcrypt hashing, JWT (pyjwt), `get_current_user`, `require_role`.
- `shared/geo.py` — maps `last_seen_location` → lat/lng/zone (curated landmarks + deterministic fallback).
- `auth/router.py` — `POST /api/auth/login` (form-encoded), `GET /api/auth/me`.
- `public/router.py` — `POST /api/public/submit` (no auth; photo + fields + reporter phone; honeypot + per-IP rate limit).
- `admin/router.py` — queue list/get, `/match` (text term overlap + gender/age/zone boosts), confirm / promote / reject, `cases/{id}/reunite`, cases browse, **admin-only** staff CRUD + `analytics/summary`.
- `main.py` — lifespan seeding, router mounts, serves photos at `/api/media/photos`.

### Frontend (React) — `frontend/src/`
- `authApi.js` (separate from the FROZEN `api.js`) + `auth/AuthContext.jsx` with `RequireAuth` / `RequireRole`.
- Pages: `Login`, `PublicSubmit` (anonymous, no sidebar), `Queue` (review → run match → confirm/promote/reject), `Staff` (admin-only: accounts + analytics).
- `Layout.jsx` — role-gated nav + user/sign-out; `App.jsx` — public (`/submit`, `/login`) vs protected routes.

### State machines
- Submission: `pending → reviewing → (matched | promoted | rejected)`
- Case: `Active → Matched → Reunited` (frozen vocab)

### Verified end-to-end (Playwright UI + curl API, 0 console errors)
1. Anonymous `/submit` → "Report received #1" ✅
2. Operator login → **no** Staff nav (role gating) ✅
3. Queue → open → **Run match → 5 ranked candidates** ✅
4. Confirm → submission `matched`, case `Reunited` ✅
5. Admin login → Staff & Analytics (2500 cases, 2151 reunited) ✅
6. API: bad password → 401; operator→`/admin/staff` → 403 ✅

---

## 7. Run / demo

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000      # docs at /docs

# Frontend
cd frontend && npm install && npm run dev   # :5173
```

**Demo creds:** `admin / admin123` · `operator / operator123` · public form `/submit`
**Reset clean state:** stop backend, `rm backend/data/sangam.db` (re-seeds on start).

---

## 8. Open / next steps
- Matching is **text + attribute** based now; face-embedding scoring plugs into `/match` via `services/face_search/logic.py` when Member 1's module is ready.
- The 4 existing feature modules (Face/Voice/Sim/Routing) still need their backend routers (per `PLAN.md`); they're now staff-gated routes in the frontend.
- Nothing committed yet — pending user go-ahead for branch + commit.
- Possible future wedges from research: multilingual voice intake, QR family tags, unified cross-agency index, reunification OTP handshake.
