# SANGAM — Features & Database Build Plan

> **Decisions locked in:**
> 1. **Database:** migrate fully from local SQLite → **Supabase Postgres** (pgvector, Realtime, Storage, RLS).
> 2. **Frontend:** **three distinct surfaces** — Admin (desktop), Operator (mobile), Public (QR/PWA).
>
> Supabase project: `cpbmfnjeqtnjzeoogpoo` · URL `https://cpbmfnjeqtnjzeoogpoo.supabase.co`

This plan maps every feature in `ROLES.md` to concrete tables, endpoints, and screens, marks what
already exists vs. what's new, and gives a build order.

---

## 0. Where we are today (honest baseline)

**Backend (FastAPI + SQLite `sangam.db`):**
- ✅ `auth` — JWT login, `/me`, bcrypt, `require_role`.
- ✅ `public` — anonymous `POST /submit` (photo upload, honeypot, per-IP rate limit).
- ✅ `admin` — submissions queue (list/get/**match**/confirm/promote/reject), cases (list/reunite), staff CRUD, analytics summary. *Matching is text-token overlap + attribute boosts.*
- ✅ `shared` — `Case` model, SQLite `cases`/`staff`/`submissions`, `geo.resolve()` (zone tagging).
- ✅ Data seeded: **2,500 cases**. CSVs present for CCTV (1,280), Police (14), Chokepoints (85), Zones (32) — **not yet in DB** (only zones used by geo).

**Frontend (React, single staff app):**
- ✅ Pages: Dashboard, Queue, Staff, Login, PublicSubmit.
- 🟡 FaceSearch, VoiceMatch, Simulation, Routing — **placeholder UIs** wired to stub endpoints (`face/search`, `voice/match`, `sim/run`, `routing/best`) that **don't exist** in the backend.
- ❌ No "check my report" for public, no found-persons gallery, no operator mobile surface, no realtime push.

**Gap to close:** move data to Supabase, split into 3 surfaces, implement the real matching + the missing features, and wire active (realtime) match push.

---

## 1. Database setup (Supabase) — the foundation

Everything else depends on this. Build it first, via the Supabase MCP (`apply_migration`).

### 1.1 Extensions
- `vector` (pgvector) — face embedding similarity.
- `pg_trgm` — fuzzy text/name search (handles the messy 15%-missing-name data).

### 1.2 Tables

**`profiles`** (staff identity; linked to Supabase Auth `auth.users`)
| col | type | notes |
|---|---|---|
| id | uuid PK → auth.users.id | |
| role | text check (`admin`/`operator`) | drives RLS + UI |
| name | text | |
| zone | text null | operator's assigned zone |
| created_at | timestamptz default now() | |

**`cases`** (the canonical cross-center registry — the heart)
- All `Case` fields from `schema.py` (case_id, type, name, name_normalized, gender, age_band, language, state, district, last_seen_location, lat, lng, zone, reporting_center, reporter_mobile, physical_description, photo_path, audio_path, transcript, transcript_en, status, reported_at, remarks).
- `face_embedding vector(512)` — replaces the TEXT blob; real similarity.
- `created_by uuid null → profiles.id`, `assigned_zone text null`.
- Indexes: `ivfflat (face_embedding vector_cosine_ops)`, `gin (name_normalized gin_trgm_ops)`, btree on `status`, `zone`, `type`.

**`submissions`** (public inbox awaiting review — keep current shape)
- missing_name, gender, age_band, last_seen_location, physical_description, photo_path, reporter_name, reporter_phone, lat, lng, zone, review_status (`pending`/`reviewing`/`matched`/`promoted`/`rejected`), reviewed_by, reviewed_at, decision_note, matched_case_id, created_case_id, source_ip, created_at.

**`matches`** (NEW — powers active push + admin review queue + audit of matches)
| col | type | notes |
|---|---|---|
| id | uuid PK | |
| case_id | text → cases | |
| submission_id | int → submissions (null) | |
| candidate_case_id | text → cases (null) | cross-center case↔case match |
| method | text | `face`/`voice`/`text` |
| score | float | |
| status | text | `proposed`/`confirmed`/`rejected` |
| created_at | timestamptz | |

**Geo reference (NEW — seeded from CSVs):**
- `cameras` (camera_id, lat, lng, zone) — 1,280 rows.
- `police_stations` (station_name, lat, lng, zone) — 14 rows.
- `chokepoints` (location_name, category, risk, lat, lng, zone, note) — 85 rows.
- `zones` (zone_name, centroid_lat, centroid_lng, boundary jsonb) — 32 rows.

**`audit_log`** (NEW — DPDP/PII access trail for admin)
- id, actor uuid, action, target_table, target_id, at timestamptz.

### 1.3 Storage
- Bucket **`photos`** (public-read or signed-URL) for case + submission images. Replace local `data/photos/` + the `/api/media/photos` static mount.

### 1.4 Realtime
- Enable on **`submissions`**, **`matches`**, **`cases`** → operator app subscribes and gets matches **pushed** (the passive→active flip) without polling.

### 1.5 RLS policies (enforce the ROLES.md tiers in the DB itself)
| Table | anon (public) | operator | admin |
|---|---|---|---|
| submissions | INSERT only; SELECT own by id+phone | SELECT/UPDATE | ALL |
| cases | SELECT non-PII view only (gallery) | SELECT/UPDATE/INSERT (zone) | ALL |
| matches | — | SELECT/UPDATE (zone) | ALL |
| profiles, staff | — | SELECT self | ALL |
| geo tables | SELECT | SELECT | ALL |
| audit_log | — | — | SELECT |

- Public reads go through a **`cases_public` view** exposing only non-PII columns (photo, gender, age_band, zone, status) for the found-persons gallery.

### 1.6 Seeding
1. `cases` ← `Synthetic_Missing_Persons_2500.csv` (port the existing `_seed_cases` logic; run zone resolution).
2. Geo tables ← the four CSVs (one `apply_migration`/insert each).
3. `profiles` ← demo `admin` + `operator` via Supabase Auth users.

---

## 2. Backend refactor: SQLite → Supabase

Keep the router/contract structure; swap the data layer.

- Replace `shared/db.py` `get_conn()`/sqlite calls with a Supabase client (`supabase-py`) or direct Postgres (`psycopg`) using the service-role key (server-side only, from env `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`).
- `auth`: switch staff login to **Supabase Auth** (email/password) → return session; `profiles.role` gates routes. (Keep current JWT as fallback if Auth wiring runs long.)
- `public/submit`: insert into `submissions` via Supabase; upload photo to Storage `photos` bucket.
- `admin` routes: same logic, Supabase queries. Matching reads `cases` from Postgres.
- Photos: return Storage public/signed URLs instead of `/api/media/...`.

---

## 3. Features by surface (what to build, how)

Legend: ✅ exists · 🟡 partial · ❌ new

### 3.A PUBLIC — QR → mobile web (PWA)

| Feature | Status | How we build it |
|---|---|---|
| Landing (Report / Check), multi-language | ❌ | New `public/` Vite app (or route group). Hindi/Marathi/English toggle. QR posters deep-link here. |
| Report a missing person | ✅ | Reuse `POST /api/public/submit`; point photo upload at Supabase Storage. |
| Check my report (status) | ❌ | New `GET /api/public/status?phone=&id=` → reads `submissions` + linked case status via RLS-safe view. Returns Active/Match found/Reunited + which center. |
| Found-persons gallery (anonymized) | ❌ | New `GET /api/public/gallery?zone=` → `cases_public` view (found type, non-PII). "This is them" → creates a `matches` row (`proposed`) for an operator. |
| Case ID + SMS/QR receipt | 🟡 | On submit, return case ID + render a QR; SMS is a stretch (Twilio/console-stub for demo). |

### 3.B OPERATOR — mobile app (field kiosk)

| Feature | Status | How we build it |
|---|---|---|
| Login (operator) | ✅ | Supabase Auth; role `operator`. |
| Home / my queue (pushed matches first) | 🟡 | New mobile layout. Subscribe to Realtime `matches`/`submissions` for their `zone`. Reuses `/api/admin/submissions`. |
| File report (missing/found) + photo | 🟡 | New operator-facing form (mobile-first). Insert into `cases` directly (operators are trusted) with zone auto-tag. |
| Voice intake (transcribe+translate) | ❌ | New `POST /api/voice/match` — faster-whisper transcribe → translate (Claude API) → store `transcript`/`transcript_en` → text-match candidates. Implements the stubbed endpoint. |
| Photo / face + clothing search | 🟡→❌ | New `POST /api/face/search` — InsightFace embedding → pgvector cosine query over `cases.face_embedding` → matches with camera/zone + nearest police station. Implements the stub for real. |
| Match detail → Route to / Confirm reunion | 🟡 | Match detail screen: side-by-side, score, one-tap "Route to" (calls routing), "Confirm reunion" → `/api/admin/cases/{id}/reunite`. |
| Offline-first capture → sync | ❌ | PWA service worker + IndexedDB queue; flush to API on reconnect. (Stretch; demo can show queued→sent.) |

### 3.C ADMIN — desktop (control room)

| Feature | Status | How we build it |
|---|---|---|
| Live dashboard + map | 🟡 | Desktop layout. Map (react-leaflet/deck.gl) plotting zones, cameras, police, chokepoints (from geo tables) + live case pins via Realtime. |
| Case registry (all zones, filter/sort) | ✅ | `GET /api/admin/cases` (add zone/type/age/language filters). |
| Match review queue | 🟡 | `matches` table + existing submission match flow; confirm/reject/merge. |
| Simulation (hotspots) | ❌ | New `POST /api/sim/run` — Monte Carlo over case density × chokepoint risk → hotspot heatmap + resource needs. Implements the stub. |
| Routing / KG console | ❌ | New `POST /api/routing/best` — networkx graph over zones/police/chokepoints; shortest path **avoiding high-risk chokepoints**. Implements the stub. |
| Analytics ("top transfer nodes = X%") | 🟡 | Extend `/api/admin/analytics/summary` with chokepoint-correlated separation stats. |
| Staff & zone management | ✅ | `GET/POST/DELETE /api/admin/staff` (+ assign `zone`). |
| Audit log view | ❌ | `GET /api/admin/audit` over `audit_log`; write entries on PII reads/edits. |
| Zone alert broadcast | ❌ | `POST /api/admin/broadcast` → inserts a row operators' Realtime subscription picks up. |

---

## 4. The matching engine (the core IP)

Three matchers, all writing into `matches`, surfaced to operators via Realtime:
1. **Text/fuzzy** (✅ exists) — token overlap + gender/age/zone boosts; upgrade with `pg_trgm` on `name_normalized`.
2. **Face** (❌) — InsightFace 512-d embeddings, pgvector cosine, threshold → candidates with camera/zone/nearest-station.
3. **Voice** (❌) — whisper transcript → translate → feed text matcher cross-language.

**Active loop:** any new `submission`/`case` → run matchers → insert `proposed` matches → Realtime pushes to the right zone's operator → operator confirms → case `Reunited`. This is the demo's spine.

---

## 5. Build order (phased)

| Phase | Deliverable |
|---|---|
| **P1 — DB foundation** | Supabase extensions, all tables, RLS, Storage bucket, Realtime enabled, seed cases + 4 geo tables + demo staff. |
| **P2 — Backend swap** | `shared/db.py` → Supabase; auth via Supabase Auth; public/admin routers reading/writing Postgres + Storage. Verify existing flows still pass. |
| **P3 — Public surface** | PWA: landing, report (live), **check status**, gallery. QR deep-link. |
| **P4 — Operator mobile** | Mobile layout, my-queue with Realtime push, file report, match detail, confirm reunion. |
| **P5 — Matching** | Real `/api/face/search` (pgvector) + `/api/voice/match` (whisper+translate). |
| **P6 — Admin desktop** | Map dashboard, review queue, `/api/sim/run`, `/api/routing/best`, analytics, audit, broadcast. |
| **P7 — Polish/demo** | Realtime end-to-end, the grandmother demo script, seed a guaranteed-match pair. |

---

## 6. Cross-cutting

- **Auth:** Supabase Auth for staff (admin/operator); anon key for public (RLS insert-only).
- **Secrets:** `SUPABASE_URL`, `SUPABASE_ANON_KEY` (frontend), `SUPABASE_SERVICE_KEY` (backend only) in `.env`.
- **Compliance (DPDP):** consent line on public form, audit_log on PII access, non-PII `cases_public` view for the gallery.
- **Demo safety:** seed one submission that deterministically matches one `cases` row so the live match always fires.
- **Contracts:** the four stub endpoints (`face/search`, `voice/match`, `sim/run`, `routing/best`) in `api.js` stay as-is — we're implementing them, not renaming, so the frozen contract holds.

---

## 7. Open follow-ups (decide as we go)
- Operator file-report: write straight to `cases`, or also through the review queue? (Plan assumes trusted → direct to `cases`.)
- SMS provider for public receipts (Twilio vs console-stub for demo).
- Face image source for CCTV: gallery-folder stand-in (per `PLAN.md §10`) vs uploaded photos only.
