# SANGAM — Supabase Migration & Deploy Plan (executing now)

> **Architecture:** Supabase-native. The React frontend talks **directly** to Supabase
> (Auth + Postgres + Storage via RLS). Matching runs as a Postgres **RPC**. FastAPI is dropped
> from the hosted path. Frontend deploys to **Vercel**.
>
> Supabase project `cpbmfnjeqtnjzeoogpoo` · `https://cpbmfnjeqtnjzeoogpoo.supabase.co`

## What changes vs. today
- **Auth:** custom bcrypt+JWT (FastAPI) → **Supabase Auth** (email/password). Usernames map to
  emails: `admin → admin@sangam.local`, `operator → operator@sangam.local`.
- **Data:** SQLite (`sangam.db`) → **Supabase Postgres** (`cases`, `submissions`, `profiles`).
- **Matching:** Python token-overlap → **`match_submission()` Postgres RPC** (same scoring logic:
  Jaccard token overlap + gender/age/zone boosts).
- **Photos:** local `data/photos` + static mount → **Supabase Storage** bucket `photos`.
- **Frontend calls:** `fetch('/api/...')` → `@supabase/supabase-js` queries / RPC / auth.

## Tables
- **`profiles`** — `id uuid PK → auth.users`, `role (admin|operator)`, `name`, `created_at`.
- **`cases`** — full `Case` model (case_id PK, type, name, name_normalized, gender, age_band,
  language, state, district, last_seen_location, lat, lng, zone, reporting_center, reporter_mobile,
  physical_description, photo_path, status, reported_at, remarks). Indexed: trgm on
  `name_normalized`, btree on status/zone/type.
- **`submissions`** — public inbox (missing_name, gender, age_band, last_seen_location,
  physical_description, photo_path, reporter_name, reporter_phone, lat, lng, zone, review_status,
  reviewed_by, reviewed_at, decision_note, matched_case_id, created_case_id, created_at).

## RLS
- `submissions`: **anon INSERT** (public report) · authenticated SELECT/UPDATE.
- `cases`: authenticated SELECT/UPDATE/INSERT (PII — staff only).
- `profiles`: authenticated SELECT.
- Staff create/delete uses **service role inside an Edge Function** (`staff-admin`), gated to admins.

## RPC
- `match_submission(p_sub_id, p_top_n)` → ranked candidate cases (security definer).

## Seeding
- `cases` ← 2,500 rows from `backend/data/sangam.db` (geo already resolved) via a one-shot Python
  script using the publishable key (temporary anon-insert policy, then revoked).
- Staff ← `admin@sangam.local` / `operator@sangam.local` (pgcrypto) + profiles.

## Frontend
- `src/supabase.js` client (URL + publishable key from `VITE_` env).
- Rewrite `authApi.js` + `AuthContext` to Supabase Auth; `Queue`/`Staff`/`PublicSubmit` to Supabase
  queries + RPC + Storage. Remove the Vite `/api` proxy dependency.

## Deploy
- Vercel: SPA build, env `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`, rewrite all routes → `index.html`.

## Demo creds
`admin@sangam.local / admin123` · `operator@sangam.local / operator123` · public form at `/submit`
