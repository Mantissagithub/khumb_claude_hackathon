# Agent Brief — OPERATOR App (Lost & Found Center)

You are polishing the **Operator** surface of SANGAM. You own **`frontend/src/operator/`** only.

---

## 1. Project context (read first)
**SANGAM** reunites people separated at the **Kumbh Mela** (~80M people, mostly elderly/rural). The
old system is **passive**; SANGAM makes it **active** — any report filed anywhere is matched across
all centers, and an operator confirms the match.

**You are the operator: a volunteer/police staffer at a help-desk kiosk.** For most found people
(elderly, phoneless), *you are the interface*. Optimize for fast, one-handed, possibly-offline use.

Three surfaces, one app, separate link paths:
- Public (`/`) · **Operator (`/ops`)** ← you · Admin (`/admin`)

**Stack:** React 19 + Vite, Tailwind v4, shadcn/ui, Supabase (Postgres + Auth + Storage + Edge
Functions). Deployed on Vercel.
**Live:** https://frontend-ebon-gamma-42.vercel.app
**Supabase:** project `cpbmfnjeqtnjzeoogpoo` · `https://cpbmfnjeqtnjzeoogpoo.supabase.co`
anon key `sb_publishable_BAZV-UJzryDm396f1i3FAg_54287XrC` (in `frontend/.env`). Supabase MCP is in
`.mcp.json`.

Read `STRUCTURE.md`, `PUBLIC_PLAN.md`, `FEATURES_PLAN.md` at the repo root.

---

## 2. Your surface

**Link base:** `/ops` · **Login:** `/ops/login` · open to **any staff** (operator or admin).

**Feature scope (Ops = find & reunite):** Public Reports review, Review Queue (legacy), Face Search,
Voice Match.

**Routes** (`frontend/src/operator/OperatorApp.jsx`):
- `/ops` Public Reports (index) · `/ops/queue` · `/ops/face` · `/ops/voice` · `/ops/login`

---

## 3. Your files (`frontend/src/operator/`)
```
OperatorApp.jsx          routes (RequireAuth loginPath="/ops/login")
components/Layout.jsx     left-nav (Public Reports, Review Queue, Face, Voice)
pages/Login.jsx          staff sign-in → /ops
pages/Reports.jsx        ★ MAIN: review public reports → match → confirm/reunite/reject
pages/Queue.jsx          legacy: review public `submissions` inbox
pages/FaceSearch.jsx     PLACEHOLDER (calls a stub endpoint that 404s)
pages/VoiceMatch.jsx     PLACEHOLDER (stub)
```

**Data (from `@/shared/authApi.js`, staff session):**
- Reports: `listReports(status)`, `matchReport(id)`, `confirmReportMatch(id, source, refId, note)`,
  `rejectReport(id)`, `reuniteReport(id)`.
- Legacy submissions: `listSubmissions`, `getSubmission`, `runMatch`, `confirmMatch`, `promote`,
  `reject`, `reunite`. Cases: `listCases`. `mediaUrl(path)` for photos.

**How matching works (already built & verified):** `matchReport` calls the `match_report` Postgres
RPC — it ranks the opposite-direction reports (a `found` for a `seeking`, etc.) **and** the
2,500-case registry, by token overlap + gender/age/zone. Confirming calls `confirm_report_match`,
which flips both reports to `found` and copies the found photo/center/geo onto the family's report so
the **public** app shows it.

**Backend you rely on:** tables `reports`, `submissions`, `cases`; RPCs `match_report`,
`confirm_report_match`, `reject_report`, `reunite_report`, `match_submission`. RLS already gates
these to staff (`is_staff()`).

---

## 4. Rules
- **Edit only `frontend/src/operator/`.** Don't touch `public/`, `admin/`, `App.jsx`, `main.jsx`.
- `shared/` is shared across all three agents — change only if unavoidable, and announce it.
- Imports: `@/shared/...` and `@/operator/...`. (`@` → `src`.)
- Run: `cd frontend && npm install && npm run dev` → http://localhost:5173/ops/login.

## 5. Credentials
- **Operator:** username `operator` · password `operator123`
- (Admin `admin` / `admin123` can also sign in here.)

## 6. Suggested polish (your call on priority)
- **Mobile-first kiosk layout** — the left sidebar is desktop; make `/ops` excellent on a tablet/phone.
- **Reports review UX**: clearer match cards, confidence visualization, side-by-side photos, quick
  "Confirm & route to center".
- **Face Search / Voice Match are placeholders** that hit dead `/api/...` stubs. Either implement for
  real (face = Supabase `pgvector` over uploaded photos; voice = transcribe+translate) or replace the
  pages with a working text/photo search over `reports` + `cases`.
- A **found-persons board** for the operator's zone; reunion confirmation flow polish.
- Loading/empty/error states; keyboard-fast data entry.
