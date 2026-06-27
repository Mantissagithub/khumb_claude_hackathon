# Agent Brief — ADMIN App (Control Center)

You are polishing the **Admin** surface of SANGAM. You own **`frontend/src/admin/`** only.

---

## 1. Project context (read first)
**SANGAM** reunites people separated at the **Kumbh Mela** (~80M people, mostly elderly/rural). The
old system is **passive**; SANGAM makes it **active** — reports are matched across all centers. The
**admin is the control room**: oversight across all 32 zones, analytics, staff management, and
operations planning (simulation + routing). Desktop-first.

Three surfaces, one app, separate link paths:
- Public (`/`) · Operator (`/ops`) · **Admin (`/admin`)** ← you

**Stack:** React 19 + Vite, Tailwind v4, shadcn/ui, Supabase (Postgres + Auth + Storage + Edge
Functions). Deployed on Vercel.
**Live:** https://frontend-ebon-gamma-42.vercel.app
**Supabase:** project `cpbmfnjeqtnjzeoogpoo` · `https://cpbmfnjeqtnjzeoogpoo.supabase.co`
anon key `sb_publishable_BAZV-UJzryDm396f1i3FAg_54287XrC` (in `frontend/.env`). Supabase MCP is in
`.mcp.json` — use it to inspect/alter the DB.

Read `STRUCTURE.md`, `FEATURES_PLAN.md`, `ROLES.md` at the repo root.

---

## 2. Your surface

**Link base:** `/admin` · **Login:** `/admin/login` · **admin role required** (the whole area is
gated with `RequireAuth role="admin"`).

**Feature scope (Oversight):** Dashboard, Staff & Analytics, Simulation, Routing.

**Routes** (`frontend/src/admin/AdminApp.jsx`):
- `/admin` Dashboard (index) · `/admin/staff` · `/admin/simulation` · `/admin/routing` · `/admin/login`

---

## 3. Your files (`frontend/src/admin/`)
```
AdminApp.jsx             routes (RequireAuth loginPath="/admin/login" role="admin")
components/Layout.jsx     left-nav (Dashboard, Staff & Analytics, Simulation, Routing)
pages/Login.jsx          admin sign-in → /admin
pages/Dashboard.jsx      ★ live stats (analytics_summary) + recent cases (REAL data)
pages/Staff.jsx          manage staff accounts + analytics (REAL)
pages/Simulation.jsx     PLACEHOLDER (calls a stub endpoint that 404s)
pages/Routing.jsx        PLACEHOLDER (stub)
```

**Data (from `@/shared/authApi.js`, staff session):**
- `analytics()` → `analytics_summary` RPC (cases_total, by_status, submissions, top_zones).
- `listCases(params)` → registry browse. `listStaff()` → `staff_view`.
- `createStaff(body)` / `deleteStaff(id)` → the `staff-admin` Edge Function (service role,
  admin-gated). Roles are `operator` | `admin`.

**Backend you rely on:** tables `cases` (2,500 rows: ~349 Active, ~2,151 Reunited), `reports`,
`submissions`, `profiles`; RPC `analytics_summary`; view `staff_view`; Edge Function `staff-admin`.

**Untapped data for you (CSVs in `data/data/`, NOT yet in the DB):** `CCTV_Locations.csv` (1,280
cameras), `Police_Stations.csv` (14), `Chokepoints_Parking.csv` (85, with risk levels),
`Zone_Boundaries.csv` (32 zones). Loading these into Supabase (use the Supabase MCP `apply_migration`)
unlocks a **map dashboard, simulation hotspots, and routing** — the biggest wins for this surface.

---

## 4. Rules
- **Edit only `frontend/src/admin/`.** Don't touch `public/`, `operator/`, `App.jsx`, `main.jsx`.
- `shared/` is shared across all three agents — change only if unavoidable, and announce it.
- If you add geo tables/RPCs in Supabase, that's fine (shared backend) — but coordinate schema
  changes so you don't collide with the others. Prefer additive migrations.
- Imports: `@/shared/...` and `@/admin/...`. (`@` → `src`.)
- Run: `cd frontend && npm install && npm run dev` → http://localhost:5173/admin/login.

## 5. Credentials
- **Admin:** username `admin` · password `admin123`
- (Operator `operator` / `operator123` will be **denied** here — admin role only.)

## 6. Suggested polish (your call on priority)
- **Map dashboard**: load the 4 geo CSVs into Supabase, plot zones/cameras/police/chokepoints +
  live case pins (react-leaflet or an OSM/deck.gl layer).
- **Simulation** (replace placeholder): Monte Carlo over case density × chokepoint risk → hotspot
  heatmap + "pre-position staff" recommendations. The data already has risk levels.
- **Routing** (replace placeholder): shortest path between points that **avoids high-risk
  chokepoints** (the CSV has a Risk field).
- **Analytics depth**: "top 3 transfer nodes = X% of separations", reunion SLA, operator throughput.
- Audit log view (PII access) and zone-alert broadcast are stretch goals from `FEATURES_PLAN.md`.
- Desktop control-room polish: dense tables, filters, charts.
