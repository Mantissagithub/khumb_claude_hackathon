# SANGAM — User Roles, Surfaces & Capabilities

> Three surfaces, **one shared Case registry**. The shared registry *is* the cross-center fix:
> the moment any report is filed anywhere, it becomes visible to every operator and admin across
> all 32 zones, the system actively searches, and matches are pushed back. This is the
> **passive → active** flip — *"the information already exists, we just stop trapping it."*

| Role | Surface | Who | Core job |
|------|---------|-----|----------|
| **Admin** | Desktop (control room) | Authority supervisors, zone commanders | See the whole picture, direct resources |
| **Operator** | Mobile app | Police / volunteers at center kiosks | File reports, run searches, confirm matches in the field |
| **Public** | QR → mobile web (PWA, no install) | Any family member with a phone | Self-register a report, track status, find their case |

---

## 1. ADMIN — Desktop (control room / command center)

**Who:** Authority supervisors and zone commanders. They don't file individual reports — they
oversee all 32 zones and direct resources.

### Screens & what they see
- **Live dashboard / map** — all 32 zone polygons, 4,079 cameras, 14 police stations, and 85
  chokepoints plotted. Live case pins (missing = red, found = green, reunited = grey). Counters:
  active cases, matches today, average reunion time, unresolved %.
- **Case registry table** — every case across every center. Filter/sort by zone, type, age band,
  language, status, and age of case. The cross-center view no operator has today.
- **Match review queue** — system-proposed matches (face/voice) above a confidence threshold,
  awaiting human confirmation.
- **Simulation screen** — run crowd/separation simulations; heatmap of predicted hotspots over
  chokepoints + transfer nodes; resource recommendations.
- **Routing / KG console** — ask department queries (e.g. "nearest unit to Ramkund avoiding
  high-risk chokepoints") and get the best route on the map.
- **Analytics** — separations by zone/time/chokepoint, "top 3 transfer nodes = X% of cases,"
  operator throughput, SLA on reunions.

### Actions
- Confirm / reject / merge proposed matches; de-duplicate the ~8% cross-center duplicates.
- Reassign or escalate a case to a zone or police station.
- Create operator accounts, assign operators to zones, revoke access.
- Broadcast an alert to operators in a zone (e.g. "high-risk surge at Mumbai Naka").
- Run simulations, export reports, mark cases reunited.
- Review the audit log (who viewed/edited PII — DPDP compliance).

---

## 2. OPERATOR — Mobile app (field staff at kiosks / centers)

**Who:** Police and volunteers at center desks. The operator **is the interface** for most found
people (elderly, phoneless, non-local-language). Optimize for one-handed, fast, offline-capable use.

### Screens & what they see
- **Home / my queue** — *push-notified matches first* (the active-not-passive flip), then their
  active cases, with a large "+ New Report" button.
- **File report (Missing or Found)** — minimal form: photo capture, name (optional — ~15% have
  none), gender, age band, language picker, last-seen location (auto-tagged to a zone via
  point-in-polygon), reporter mobile (optional). **Voice intake button** for non-local-language
  people → transcribe + translate.
- **Search** — upload/capture a photo → face/clothing match against the gallery; or text/voice
  search. Results ranked by score, each showing the matched name and which camera / center / zone.
- **Match detail** — side-by-side photos, confidence score, the other party's center, one-tap
  **"Route to"** (nearest police station / that camera) and **"Confirm reunion."**
- **Case detail** — full record, status, notes, history.

### Actions
- File missing/found reports (photo + voice + text); works **offline → syncs** when network returns.
- Run a search; accept or dismiss a pushed match.
- Confirm reunion, add remarks, hand off/escalate to police.
- Call the reporter (tap the mobile number).
- View their assigned zone's open found-persons board.

---

## 3. PUBLIC — QR → mobile web (PWA, no install)

**Who:** Any family member with a phone. Scan a QR poster at a center/chokepoint → instant web app,
no download.

### Screens & what they see
- **Landing (post-scan)** — two large buttons: **"Report a missing person"** / **"Check my
  report."** Hindi / Marathi / English with a language toggle. Consent line on PII (DPDP).
- **Report form** — same minimal fields as the operator's; photo upload from gallery/camera. On
  submit → a **case ID + QR/SMS** they keep.
- **Check status** — enter case ID or phone → see status (Active / Match found / Reunited) and which
  center to go to. This kills the "feel invisible / re-file" problem.
- **Found-persons gallery (optional)** — browse anonymized found-person photos for their zone to
  self-spot a relative.

### Actions
- Self-register a report (no operator needed) → enters the same shared registry.
- Track status / receive SMS or push when a match is found.
- Look up their existing report from a list by phone/ID.
- Mark "this is them" → flags an operator to confirm.

---

## Permission tiers

| Capability | Public | Operator | Admin |
|---|:---:|:---:|:---:|
| Create a report | ✅ | ✅ | ✅ |
| Read own case / status | ✅ | ✅ | ✅ |
| Search registry (face/voice/text) | partial (gallery) | ✅ (zone) | ✅ (all zones) |
| Confirm / reject a match | flag only | ✅ (zone) | ✅ (all zones) |
| Merge / de-duplicate cases | — | — | ✅ |
| Manage accounts & zone assignment | — | — | ✅ |
| Run simulation / routing console | — | — | ✅ |
| Broadcast zone alerts | — | — | ✅ |
| View audit log (PII access) | — | — | ✅ |

---

## How the geo data maps to each role

| Dataset | Admin | Operator | Public |
|---|---|---|---|
| **CCTV cameras** (4,079 pts, `Z{zone}-C{n}`) | Plot on map; match-review shows source camera | Match result → "route to this camera" | — |
| **Zone polygons** (32) | Per-zone counters & filters | Auto-tag a report's `zone` from lat/lng | Status shows which zone/center to go to |
| **Police stations** (14) | Reassign/escalate target; routing endpoints | One-tap "route to nearest station" | Shown the center to collect from |
| **Chokepoints / parking / transfer nodes** (85, with risk levels) | Simulation hotspots, analytics, routing avoidance | Surge alerts for their zone | QR posters sited at these high-traffic points |
