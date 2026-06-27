# Agent Brief — PUBLIC App (Citizen surface)

You are polishing the **Public** surface of SANGAM. You own **`frontend/src/public/`** only.

---

## 1. Project context (read first)
**SANGAM** reunites people separated at the **Kumbh Mela** (a mass pilgrimage; ~80M people, mostly
elderly/rural). The old system is **passive** — a found person sits at one center, a family waits at
another, and they only connect if a human bridges them. SANGAM makes it **active**: any report filed
anywhere is instantly matched across all centers.

There are **three surfaces** in one app (one deployment, separate link paths):
- **Public** (`/`) ← you
- **Operator / Lost & Found center** (`/ops`)
- **Admin / Control center** (`/admin`)

**Stack:** React 19 + Vite, Tailwind v4, shadcn/ui, Supabase (Postgres + Auth + Storage + Edge
Functions). Deployed on Vercel.
**Live:** https://frontend-ebon-gamma-42.vercel.app
**Supabase:** project `cpbmfnjeqtnjzeoogpoo` · `https://cpbmfnjeqtnjzeoogpoo.supabase.co`
anon key `sb_publishable_BAZV-UJzryDm396f1i3FAg_54287XrC` (already in `frontend/.env`). A Supabase
MCP server is configured in `.mcp.json` for DB inspection/changes.

Read `STRUCTURE.md` and `PUBLIC_PLAN.md` at the repo root for the full design.

---

## 2. Your surface

**Who:** citizens on their phones. **Mobile-first PWA.** Often non-literate, non-local-language,
stressed. Prioritize clarity, big touch targets, minimal typing.

**Auth boundary:**
- **Submitting a report is OPEN** — no login. The form collects a phone number as a field.
- **Viewing your reports requires phone-number login (OTP).** Demo mode: the 6-digit code is shown
  on-screen (no SMS). You only see reports tied to your phone (enforced by RLS).

**Links / routes** (`frontend/src/public/PublicApp.jsx`):
- `/` Landing · `/new` file a report · `/track` phone-OTP login · `/reports` my reports ·
  `/reports/:id` status detail

**Report types:** `lost_self` (I am lost), `seeking` (searching for someone), `found` (I found a
person — captures photo + GPS + center).

**Status shown to user:** `searching → found → reunited`. When **found**, show the matched
**center name, map pin (found_lat/lng), and the photo taken when found** (found_photo_path).

---

## 3. Your files (`frontend/src/public/`)
```
PublicApp.jsx              routes
publicApi.js               all data calls (below)
auth/PublicAuthContext.jsx phone session (supabasePublic) + RequirePhone gate
pages/Landing.jsx          two big actions + helpline 1920
pages/NewReport.jsx        3-type form, photo upload, GPS for "found"
pages/Track.jsx            phone → OTP code → verify
pages/MyReports.jsx        list of the phone's reports
pages/ReportStatus.jsx     status + found details (center/map/photo)
```

**`publicApi.js` API** (all implemented & working):
- `requestOtp(phone)` / `verifyOtp(phone, code)` → calls the `auth-phone` Edge Function; verify sets
  the public session.
- `submitReport(form)` → `submit_report` RPC (anon). `uploadPhoto(file)` → Storage `photos` bucket.
- `listMyReports()` / `getMyReport(id)` → RLS-scoped to the logged-in phone.
- `mediaUrl(path)` → public URL for a Storage photo.

**Backend you rely on** (don't change without coordinating): table `reports`; RPCs `submit_report`,
`match_report`, `confirm_report_match`; Edge Function `auth-phone`; Storage bucket `photos`. The
**operator** confirms matches → that flips your report to `found` and fills the found details.

---

## 4. Rules
- **Edit only `frontend/src/public/`.** Do not touch `operator/`, `admin/`, `App.jsx`, or `main.jsx`.
- `shared/` (ui kit, supabase client, theme) is **shared across all three agents** — change it only
  if unavoidable, and call it out.
- Imports: `@/shared/...` for shared, `@/public/...` for your own. (`@` → `src`.)
- Run: `cd frontend && npm install && npm run dev` (http://localhost:5173/). Build: `npm run build`.

## 5. Credentials
The public surface needs **no login** to submit. To test viewing, file a report with any phone
number, then go to `/track`, enter that number, and use the **demo code shown on screen**.

## 6. Suggested polish (your call on priority)
- **Multi-language** (Hindi / Marathi / English) toggle — high impact for this audience.
- Accessibility: larger fonts/targets, simpler copy, voice-over labels.
- Map polish on the Found status (currently an OSM iframe + Google directions link).
- QR-code receipt after submit; "voice description" intake for non-literate users.
- Loading skeletons, empty states, friendly errors, offline/PWA install, brand polish.
- Keep it emotionally reassuring — this is a family in distress.
