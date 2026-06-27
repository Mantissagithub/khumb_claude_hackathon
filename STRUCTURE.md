# SANGAM — Frontend Structure (3 role folders, one app)

One Vite app, one deployment, **three role surfaces on separate link paths** — organized so three
Claude Code agents can work in parallel, each owning one folder.

## Links (same deployment)
| Surface | Link base | Owner agent | Login |
|---|---|---|---|
| **Public** (citizens) | `/` | Public agent | none to submit · phone OTP at `/track` to view |
| **Operator** (Lost & Found center) | `/ops` | Operator agent | `/ops/login` (any staff) |
| **Admin** (Control center) | `/admin` | Admin agent | `/admin/login` (admin role only) |

## Folder map (`frontend/src/`)
```
src/
├── App.jsx            ← top router: mounts /ops, /admin, / (LEAD coordination point)
├── main.jsx           ← providers (LEAD)
├── index.css          ← theme tokens (shared design system)
│
├── shared/            ← SHARED — change with care; coordinate across agents
│   ├── ui/            ← shadcn components (button, card, dialog, table, …)
│   ├── components/    ← StatusBadge, PageHeader, StatCard
│   ├── lib/utils.js
│   ├── supabase.js    ← supabase (staff) + supabasePublic clients
│   ├── authApi.js     ← staff data API (reports, cases, staff, analytics)
│   ├── api.js         ← legacy stub endpoints (face/voice/sim/routing)
│   └── auth/AuthContext.jsx   ← staff auth + RequireAuth(loginPath, role)
│
├── public/            ← PUBLIC AGENT owns this folder
│   ├── PublicApp.jsx          ← public routes
│   ├── publicApi.js           ← open submit + phone-OTP + my-reports
│   ├── auth/PublicAuthContext.jsx
│   └── pages/ (Landing, NewReport, Track, MyReports, ReportStatus)
│
├── operator/          ← OPERATOR AGENT owns this folder
│   ├── OperatorApp.jsx        ← operator routes
│   ├── components/Layout.jsx  ← operator nav (Public Reports, Queue, Face, Voice)
│   └── pages/ (Reports, Queue, FaceSearch, VoiceMatch, Login)
│
└── admin/             ← ADMIN AGENT owns this folder
    ├── AdminApp.jsx           ← admin routes
    ├── components/Layout.jsx  ← admin nav (Dashboard, Staff, Simulation, Routing)
    └── pages/ (Dashboard, Staff, Simulation, Routing, Login)
```

## Rules for parallel work
1. **Each agent only edits its own folder** (`public/`, `operator/`, or `admin/`).
2. **`shared/` is the only cross-agent surface.** Any change there → announce it; it affects everyone.
3. **`App.jsx` + `main.jsx`** are owned by the integration lead. Each role's routes live inside that
   role's `*App.jsx` — adding a page = edit only your own `*App.jsx`, no touch to the top router.
4. Imports: `@/shared/...` for shared, `@/public|operator|admin/...` for role-local. The `@` alias
   points to `src`.

## Feature split (Ops vs Oversight)
- **Operator:** Public Reports review (match → confirm → reunite), Review Queue, Face Search, Voice Match.
- **Admin:** Dashboard, Staff & Analytics, Simulation, Routing.
- Operator pages are open to **any** staff; the whole **Admin** area requires the `admin` role.

## Backend (shared by all three) — Supabase `cpbmfnjeqtnjzeoogpoo`
Tables `cases`, `reports`, `submissions`, `profiles`, `otp_codes`, `phone_users`; RPCs
`submit_report`, `match_report`, `confirm_report_match`, `reject_report`, `reunite_report`,
`analytics_summary`, `match_submission`; Edge Functions `auth-phone`, `staff-admin`. RLS gates staff
tables behind `is_staff()`; public reports scoped by phone claim.

## Verified live
- `/` → public landing · `/ops` → "Lost & Found Center" · `/admin` → "Control Center" (admin-only).
