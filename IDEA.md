# Sangam — Technical Plan

**A unified, offline-first missing-persons registry for Kumbh Mela 2027**
Claude Impact Lab, Mumbai 2026 — Missing Persons at Kumbh Mela 2027

> *Sangam* (confluence) — bringing every lost-and-found center into one stream so a person found at Center A is instantly visible to a family searching at Center B.

---

## 1. Problem → Goal

80M+ pilgrims; thousands separated daily, mostly elderly and rural. Today each lost-and-found center is an island: a found person logged at Center A is invisible to a family searching at Center B. There is **no cross-center search and no de-duplication**.

**Goal:** a single searchable registry across all centers that
1. matches a *found* report to the right *missing* report (and vice-versa) in seconds,
2. collapses duplicate reports of the same person filed at different centers,
3. works when the network is down, and
4. is usable by a phoneless, non-literate pilgrim through a human operator.

**Success metrics**
- Cross-center match recall on the 8% known duplicates in `Synthetic_Missing_Persons_2500.csv` (target: catch ≥ 90% as match candidates in the top-5).
- Median time-to-match suggestion < 2 s per query on a center laptop.
- Zero data loss during a network outage (offline writes reconcile cleanly).
- Operator can file a complete report for a phoneless, non-literate person in < 90 s.

---

## 2. Solution Overview

A **local-first registry node** runs at every lost-and-found center (laptop/tablet/kiosk). Each node:
- captures reports (missing *and* found) in a structured, multilingual form,
- runs a **candidate-matching engine** locally so it works offline,
- syncs to a central registry (and peer nodes) whenever connectivity returns.

A **central registry** holds the merged, de-duplicated view and serves cross-center search to operators, a public help-desk view, and PA/announcement workflows.

```
 Pilgrim / Family ─► Operator Kiosk (multilingual, voice-assisted form)
                          │
                  ┌───────▼────────┐      offline-first, CRDT log
                  │  Center Node    │◄──────────────────────────────┐
                  │  - local DB     │                                │
                  │  - match engine │        sync when online        │
                  └───────┬─────────┘                                │
                          │                                          │
                  ┌───────▼─────────────── Central Registry ────────┴───┐
                  │  merged registry · cross-center search · dedup queue  │
                  │  geo-context (zones/CCTV/chokepoints) · audit log     │
                  └──────────────────────────────────────────────────────┘
```

---

## 3. System Design

### 3.1 Center Node (offline-first)
- **Local store:** SQLite (single file, zero-admin, durable). Holds all reports authored locally plus a synced read-replica of the registry for offline search.
- **Write model:** every create/update is an append-only **event** with a node id + logical clock (Lamport/HLC). This makes sync conflict-free — concurrent edits merge instead of overwriting (CRDT-style last-writer-wins per field, with a manual-merge queue for conflicts).
- **Match engine:** runs locally over the synced replica so an operator gets candidate matches even with no network.
- **PWA UI:** installable, works fully offline, IndexedDB cache as fallback when no laptop SQLite is available.

### 3.2 Central Registry
- **Store:** PostgreSQL + the `pg_trgm` and `pgvector` extensions (fuzzy text + embedding search in one place). PostGIS for geo queries.
- **Sync API:** pull/push of event logs (idempotent by event id). A reconciler applies events, rebuilds the materialized "current state" per case, and feeds the **dedup queue**.
- **Search API:** `/match` (find candidates for a report), `/search` (operator free-text + filters), `/case/:id` (full history + audit trail).

### 3.3 Connectivity reality
Networks collapse near ghats and on snan days. Therefore: **node works 100% standalone**; sync is best-effort and resumable. Nodes can also gossip peer-to-peer over the same LAN/hotspot so a cluster of nearby centers stays consistent even when the uplink to central is down.

---

## 4. Data Pipeline

Grounded in the provided datasets.

### 4.1 Ingest & normalize (`Synthetic_Missing_Persons_2500.csv` schema)
For each report (`case_id, reported_at, missing_person_name, gender, age_band, state, district, language, last_seen_location, reporting_center, reporter_mobile, physical_description, status, resolution_hours, is_duplicate_report, remarks`):
1. **Clean & standardize** — trim, unicode-normalize names; canonicalize `state`/`district`/`language` to controlled vocabularies; normalize `reporter_mobile` to E.164.
2. **Handle missingness** (15% no name, 20% no mobile) — never block a report on a missing field; record what *is* known and let matching lean on the rest.
3. **Geocode `last_seen_location`** to the nearest zone using `Zone_Boundaries.csv` centroids; attach candidate `Zone Area N`.
4. **Structure the free-text `physical_description`** — extract attributes (garment, color, accessories like "rudraksha mala", "tilak") into tags via a small NER/keyword pass for matching; keep raw text too.

### 4.2 Enrich with geography
- **Zones** (`Zone_Boundaries.csv`): assign every report a zone from `last_seen_location`.
- **CCTV** (`CCTV_Locations.csv`, 1,280 cams / 32 zones): list cameras near the last-seen point so operators know where footage *could* exist (we store no footage).
- **Chokepoints/Parking** (`Chokepoints_Parking.csv`, 85 points): separations cluster at chokepoints and transfer nodes — use these to rank likely drift locations and to place help points.
- **Police** (`Police_Stations.csv`, 14): route a found person/family to the nearest station.

### 4.3 Index for matching
- Trigram + phonetic index on names; embedding vector on the structured description; categorical indexes on gender/age_band/state/district/language/zone.

---

## 5. Matching & De-duplication Engine (core)

The 8% `is_duplicate_report=True` rows are our ground truth for tuning. The same engine powers both *cross-center dedup* and *missing↔found matching*.

### 5.1 Blocking (cheap filter first)
Reduce comparisons from O(n²) to manageable buckets. Block on coarse keys: `gender × age_band × (zone OR district)`. Anyone in the same block is a comparison candidate.

### 5.2 Scoring (weighted, explainable)
For each candidate pair compute a 0–1 score from per-field similarities:

| Signal | Method | Weight |
|---|---|---|
| Name | trigram + phonetic (Indic-aware) similarity | high (when present) |
| Mobile | exact / normalized match | very high (when present) |
| Age band | exact / adjacent-band partial | medium |
| Gender | exact | low–medium |
| State + district | exact / hierarchical | medium |
| Language | exact | low |
| Last-seen zone | same / adjacent zone via geography | medium |
| Physical description | embedding cosine + shared attribute tags | medium–high |
| Time proximity | closeness of `reported_at` | low |

Weights are **dynamic**: if name and mobile are blank (common here), weight shifts to description embedding + geo + demographics. The score is a transparent sum so every match shows *why* it matched — essential for operator trust and responsible use.

### 5.3 Decision
- **score ≥ T_high** → auto-flag as likely duplicate/match → goes to operator's review queue (never auto-merged silently).
- **T_low ≤ score < T_high** → shown as ranked candidates during search.
- **< T_low** → ignored.
Thresholds tuned against the labeled duplicates to maximize recall at acceptable precision.

### 5.4 Optional vision assist (pre-trained only)
Per the brief — **use pre-trained models, don't train from scratch.** If a photo is captured at intake, run a pre-trained face-embedding model on-device to add a face-similarity signal. Strictly opt-in, consent-logged, embeddings stored not raw photos where feasible. The system is fully functional without it.

### 5.5 Human in the loop
Matches are **suggestions**. An operator confirms a merge; confirmation writes an auditable event. This keeps accountability with people and prevents wrong-merge harm.

---

## 6. UX for the Real User

The at-risk group is elderly, rural, multilingual, often phoneless and non-literate. So the primary interface is an **operator-driven kiosk**, not a consumer app.

- **Multilingual, voice-first form:** operator (or pilgrim) speaks; speech-to-text + on-screen language toggle (Marathi/Hindi/Telugu/Maithili/… per the `language` field). Large icons, minimal typing.
- **Photo-optional intake** with consent.
- **Phoneless fallback:** report works with no `reporter_mobile`; reunification routes via PA announcements, the help desk, and the nearest police station (`Police_Stations.csv`).
- **Public help-desk view:** read-only cross-center search for staff at any center/desk.
- **Announcement integration:** one click generates a PA-ready announcement (matches the existing "Announcement made on PA" / "GGTalk app used" remarks workflow).

---

## 7. Privacy & Responsible Data Handling

- **Data minimization:** capture only what aids reunification; everything optional except the bare minimum.
- **Consent logged** at intake; photos/biometrics strictly opt-in.
- **Purpose-bound + TTL:** records auto-expire/archive after the mela; no long-term retention of personal data.
- **Access control + audit:** every search, view, and merge is logged to an immutable audit trail.
- **Explainable matches** (Section 5.2) so no opaque automated decision affects a person.
- **Synthetic data only** in dev/test — never seed with real PII.

---

## 8. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Center node DB | SQLite | single-file, offline, zero-admin |
| Central DB | PostgreSQL + pg_trgm + pgvector + PostGIS | fuzzy text, embeddings, geo in one engine |
| Backend | FastAPI (Python) | fast to build; great data/ML ecosystem |
| Sync | append-only event log, HLC clocks, idempotent push/pull | conflict-free offline-first |
| Frontend | React PWA (installable, offline) | works on laptop/tablet/kiosk offline |
| Matching | rapidfuzz (trigram/phonetic) + sentence-embeddings + weighted scorer | explainable, tunable, runs on CPU |
| Geo | Shapely / PostGIS over zones, CCTV, chokepoints, police | grounded in provided datasets |
| Vision (optional) | pre-trained face-embedding model | per brief: pre-trained, not from scratch |

---

## 9. Components / Workstreams

1. **Data layer** — schema, CSV ingest, normalization, geocoding to zones.
2. **Match engine** — blocking + weighted scorer + dedup queue; tune on labeled duplicates.
3. **Center node** — local SQLite, offline write log, local search UI.
4. **Sync service** — event push/pull, reconciler, conflict/merge queue.
5. **Operator UX** — multilingual voice-assisted intake, candidate review, announcement generator.
6. **Geo & routing** — nearest police station / help point, CCTV-zone hints, hotspot ranking.
7. **Privacy & audit** — consent, RBAC, audit log, TTL/archival.

---

## 10. Milestones (hackathon roadmap)

| Phase | Deliverable |
|---|---|
| **M0 — Foundation** | Repo scaffold, load all 5 CSVs, normalized schema, zone geocoding working. |
| **M1 — Matching MVP** | Blocking + weighted scorer; cross-center dedup measured against the 8% labeled duplicates; recall@5 reported. |
| **M2 — Offline node** | SQLite center node + local search UI working with no network. |
| **M3 — Sync** | Event-log push/pull + reconciler; two nodes converge after an outage; demo a found-at-A → searched-at-B reunification. |
| **M4 — UX + geo** | Multilingual voice-assisted intake, candidate review, announcement generator, nearest-police-station routing. |
| **M5 — Privacy + polish** | Consent, audit log, TTL, explainability surfaced in UI; demo script + metrics. |

---

## 11. How this maps to the judging criteria

- **Deployability at scale** — local-first nodes + best-effort sync; SQLite/Postgres scale across 32 zones and many centers.
- **Real-world fit** — directly closes the cross-center search gap, the brief's stated core problem.
- **UX for phoneless/non-literate users** — operator kiosk, voice, icons, no-mobile and no-name paths.
- **System design** — offline-first, conflict-free sync, explicit duplicate handling, robust to incomplete data.
- **Responsible data handling** — minimization, consent, TTL, audit, explainable matches, synthetic-only testing.

---

*Built for India's First Claude Impact Lab | RIIDL, Somaiya Vidyavihar University, Mumbai.*
