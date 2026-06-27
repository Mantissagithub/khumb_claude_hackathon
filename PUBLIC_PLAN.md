# SANGAM — Public Surface Plan (open submit · phone-login to view)

> **Model:** No open directory.
> - **Submitting a report is OPEN** — no login. The form just collects the reporter's phone number.
> - **Viewing your reports requires phone-number login (OTP).** You then see **only the reports tied
>   to your phone** + live status.
> - When a report is **Found**, the portal shows the **center name, geolocation (map pin), and the
>   photo taken when the person was found.**
>
> **Decisions:** Demo OTP (no SMS provider) · 3 report types · auto-match then staff-confirm.

---

## 1. Concept & flow

```
PUBLIC (no login)
  └─ [+ New report]            ← open, anonymous; phone is a form field
        ├─ I am lost (reporting myself)      → type: lost_self
        ├─ I'm searching for someone         → type: seeking
        └─ I found a lost person             → type: found  (photo + GPS + center)
              ↓ on submit: case ID receipt + "view status by logging in with this phone"

VIEW MY REPORTS (phone OTP login)
  └─ My reports (all reports filed with this phone number)
        └─ Report card → status:
              • Searching…              (active, system + staff working on it)
              • FOUND → center name · map pin (lat/lng) · found-photo · "directions"
              • Reunited                (closed)
```

**Why no directory works:** matching is done by the **system + staff**, not the crowd — so we don't
expose everyone's photos publicly. A finder's **"I found a lost person"** report supplies the
found-photo + location that the searching family later sees on their status card.

---

## 1a. Routing & links (separate paths, one deployment)

Public and staff live in the **same Vercel app** but on **distinct entry links**:

| Audience | Link | Routes |
|---|---|---|
| **Public** | root `/` | `/` (landing) · `/new` (file a report, open) · `/track` (phone-OTP login → my reports) · `/track/:id` (status detail) |
| **Staff** | `/ops` | `/ops/login` (staff sign-in) · `/ops` (dashboard) · `/ops/queue` · `/ops/face` · `/ops/voice` · `/ops/simulation` · `/ops/routing` · `/ops/staff` (admin) |

- The current `/login` (staff) and `/submit` (public) routes are **replaced** by this scheme.
- Staff routes stay behind `RequireAuth` + role gating; public `/new` is open, `/track` requires
  phone OTP.
- Two separate auth contexts: **staff** = Supabase Auth (email/password, has a `profiles` row);
  **public** = Supabase Auth phone-OTP (no `profiles` row).

---

## 2. Auth — phone OTP gates *viewing only*

Submitting never asks for login; it only collects a phone number in the form. Login (OTP) is the gate
to **view** reports tied to that phone. Real Supabase phone auth needs a paid SMS provider, so we use
a **custom OTP** that behaves identically but shows the code on-screen (one line flips to real SMS).

**`otp_codes` table:** `phone`, `code`, `expires_at`, `consumed`.

**Edge Function `auth-phone` (service role):**
- `action: "request"` → input `phone`. Generate 6-digit code (5-min expiry); ensure a Supabase Auth
  user exists for the phone (email `p<digits>@phone.sangam.local`, `user_metadata.phone = phone`).
  **Return the code** (demo only — later: SMS it, return nothing).
- `action: "verify"` → input `phone` + `code`. Validate → mark consumed → set fresh random password →
  **sign in server-side** → return `{ access_token, refresh_token }`.

**Frontend:** phone → `request` → show/enter code → `verify` →
`supabase.auth.setSession(...)` → authenticated session carrying `user_metadata.phone`.

Public users are Supabase Auth users **without** a `profiles` row (that's what separates them from
staff — see RLS).

---

## 3. Data model — `reports` table

| col | type | notes |
|---|---|---|
| id | bigint identity PK | |
| reporter_phone | text NOT NULL | **the link** — anonymous submit stores this; login matches on it |
| reporter_id | uuid null → auth.users | backfilled if/when they log in (optional) |
| report_type | text | `lost_self` \| `seeking` \| `found` |
| person_name | text null | |
| gender, age_band, language | text null | |
| description | text null | clothes, marks, etc. |
| photo_path | text null | Storage key |
| location_text | text null | last-seen (missing) / found-at (found) |
| lat, lng | double precision null | GPS — auto for `found`, optional otherwise |
| zone | text null | resolved from lat/lng |
| center_name | text null | for `found`: which help center the person is at |
| status | text | `searching` \| `found` \| `reunited` (public-facing) |
| matched_report_id | bigint null → reports | links seeking ↔ found |
| review_status | text | staff: `pending`\|`reviewing`\|`confirmed`\|`rejected` |
| reviewed_by | uuid null → profiles | |
| reviewed_at, created_at | timestamptz | |

**Found details shown to the family** = the matched **found** report's `photo_path`, `center_name`,
`lat`, `lng`.

---

## 4. RLS (⚠️ includes a required hardening)

**Problem:** today `cases`/`submissions` allow **any authenticated** user to read. Once the public are
authenticated users, they could read staff PII. Gate staff tables to staff only.
- Add `is_staff()` → `exists(select 1 from profiles where id = auth.uid())`.
- Repoint `cases` + `submissions` policies from `to authenticated` → `using (is_staff())`.

**`reports` policies:**
- **INSERT: open** — `to anon, authenticated with check (true)` (submitting needs no login).
- **SELECT/UPDATE (own):** `reporter_phone = (auth.jwt() -> 'user_metadata' ->> 'phone')` **OR**
  `is_staff()`.
- staff UPDATE (confirm/reject/link): `is_staff()`.

**`otp_codes`:** Edge Function only (service role); no client access.

---

## 5. Matching (auto + staff-confirm)

On a new `reports` insert:
1. Matching runs:
   - `seeking` / `lost_self` → match against `found` reports **and** the `cases` registry.
   - `found` → match against open `seeking` / `lost_self` reports.
2. Candidates saved for staff (`review_status='reviewing'`).
3. Staff confirm → both reports `status='found'`, set `matched_report_id`, surface found details;
   later mark `reunited`.
4. Reuse the `match_submission` scoring (token overlap + gender/age/zone), generalized to reports.

---

## 6. Screens (mobile-first PWA)

1. **Landing** — `[+ New report]` (open) and `[View my reports]` (→ login).
2. **New report (no login)** — pick type → minimal form (photo, name, gender, age, description,
   location, **phone**). For **found**: auto-capture GPS + camera photo + center picker. On submit →
   case-ID receipt + "log in with this phone to track status."
3. **Login (only for viewing)** — phone → "Send code" → code → "Verify". (Demo: code shown.)
4. **My reports** — status cards for every report filed with this phone.
5. **Report detail / status** —
   - Searching: "we're actively searching across all centers."
   - **Found:** found-photo, center name, **map pin** (Leaflet) at lat/lng, "Get directions."
   - Reunited: closed confirmation.
6. **Header:** language toggle (Hindi/Marathi/English — fast-follow); phone + sign out when logged in.

---

## 7. Build steps

| # | Step | Where |
|---|------|-------|
| 1 | `otp_codes` + `reports` tables, `is_staff()`, RLS (incl. cases/submissions hardening) | Supabase migration |
| 2 | `auth-phone` Edge Function (request/verify, demo code, sets `user_metadata.phone`) | Supabase |
| 3 | Generalized match (reports ↔ reports/cases) + staff-confirm updates | Supabase |
| 4 | Open New-report flow (3 types, phone field, no login) + Storage upload + GPS/camera for `found` | frontend |
| 5 | Phone-OTP login + session (view gate only) | frontend |
| 6 | My reports + status detail w/ map | `src/pages/public/` |
| 7 | Staff queue reads `reports` (confirm → flips status) | `src/pages/Queue.jsx` |
| 8 | Deploy to Vercel + verify end-to-end | Vercel |

---

## 8. Scope

**v1 (build now):** open submit (3 types), phone OTP **view** login, my-reports + status, found
details (center + map + photo), auto-match → staff confirm, RLS hardening.

**Fast-follow:** multi-language, QR-receipt, SMS alert on match, "directions" deep-link, voice intake.

---

## 9. Open follow-ups
- Keep the old anonymous `/submit` page, or replace with this new open New-report flow? (Plan assumes
  **replace**, since the new one already supports anonymous submit + 3 types.)
- Should `found` reports match against the 2,500-case registry too, or only public `seeking` reports?
  (Plan assumes **both**.)
