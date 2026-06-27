# Sangam Backend — Face/Cloth + Cross-Language Voice Matching

Two features, wired end to end on the provided Kumbh Mela datasets:

1. **Face + Cloth matching** — a family uploads a photo of who they lost, OR a
   volunteer uploads a photo (and any ID they found) of an unconscious / lost
   person. The system matches the two sides — and the government registry —
   and returns *where* the matched person was reported, with the nearest
   police station and CCTV coverage.
2. **Cross-language voice matching** — a phoneless, non-literate pilgrim speaks
   in any language; we transcribe, translate, and search the registry.

Everything is **free / offline / pre-trained** (no paid APIs, no train-from-scratch),
and every optional dependency is import-guarded so the API still boots and does
text + geo matching on a bare machine.

---

## The scenario it solves

```
Family of a lost person  ──►  POST /reports/missing  (photo + details)
                                     │
Volunteer finds someone  ──►  POST /reports/found    (photo + any fetched ID)
unconscious on the ground            │
                                     ▼
                          Fusion engine matches across:
                          • the other side's live reports
                          • the government registry (2,500 records)
                                     ▼
                  Ranked, explainable matches + the person's LOCATION
                  (zone · nearest police station · nearby CCTV)
```

A found person logged at Center A becomes instantly visible to a family
searching at Center B — the core gap in today's system.

---

## Quick start

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt                      # see requirements.txt for optional groups
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs  (interactive Swagger UI)
```

Minimal install (text + geo matching only): `pip install fastapi uvicorn python-multipart pydantic rapidfuzz`.
Add `numpy Pillow` for cloth, `face_recognition` (or `deepface`) for face,
`faster-whisper` for voice.

Check what's active: `GET /health` reports which backends loaded.

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | which match backends are active |
| GET  | `/stats` | registry + live report counts |
| POST | `/reports/found` | intake a found person (photo optional) → matches |
| POST | `/reports/missing` | intake a missing report (photo optional) → matches |
| POST | `/search` | text/filter search, no upload (JSON body) |
| POST | `/voice/query` | upload audio in any language → matches |
| GET  | `/reports/{id}` | fetch a stored report (biometrics stripped) |
| GET  | `/reports/{id}/matches` | re-run matching for a stored report |

Every match result includes: `score`, a `decision` band
(`review_queue` ≥ 0.72 · `candidate` ≥ 0.40 · `weak`), a per-signal
`breakdown`, human-readable `reasons`, and a `location` block.

---

## How matching works

A single fusion score per candidate, from these signals:

| Signal | Source | Notes |
|---|---|---|
| **face** | photo → embedding (dlib/DeepFace) | live↔live only (registry has no photos) |
| **cloth** | photo colours ↔ photo colours, or photo↔text, or text↔text | maps to a shared colour vocabulary |
| **name** | fuzzy (rapidfuzz) | absent for 15% of records — handled |
| **mobile** | normalised last-10-digits exact | strong when present (20% missing) |
| **demographics** | gender + age band (adjacency-aware) + state/district + language | |
| **description** | free-text similarity | |
| **geo** | distance between resolved coordinates | last-seen text resolved via gazetteer |

**Dynamic weighting:** the score is re-normalised over only the signals that
actually exist for a pair, so a no-name / no-photo report still matches on
description + geo + demographics instead of being punished for blank fields.

**Explainable + human-in-the-loop:** nothing is auto-merged. High scores go to
an operator's review queue with the reasons spelled out; the operator confirms.

**Cloth ↔ language bridge:** photo colours and spoken/typed descriptions map to
the *same* canonical colour/garment tags (English + transliterated Hindi/Marathi),
so a photo of a saffron kurta matches a spoken "bhagwa kurta".

---

## Edge cases — handled now

- **No photo** → face signal simply drops out; text/cloth-from-text/geo carry it.
- **No name (15%) / no mobile (20%)** → dynamic weighting, no false penalty.
- **Cross-center duplicates (8%)** → `scope="dedup"` compares same-type reports.
- **No GPS** → last-seen free text is resolved to coordinates via a gazetteer
  built from chokepoint / police / zone names.
- **Unconscious / can't speak** → matched purely on photo + clothing + any
  fetched ID details (name/age go into the text signals).
- **Many people in white/saffron** → cloth is intentionally low-weighted and
  never decisive alone; combined with face/geo/demographics it still helps.
- **Multilingual speech** → Whisper auto-detects + translates before parsing.

## Edge cases — flagged, not yet fully built (see Open Questions)

- **Face fails:** no face / multiple faces / blur / occlusion (ghoonghat, veil,
  turban, mask), sunglasses, big age gap between an old printed photo and the
  person today. → need a "low-confidence face, ask for more info" path.
- **Fetched ID ≠ the person** (volunteer found a dropped bag/ID). → must not
  assume ID identity equals the found person; flag for verification.
- **Malicious / mistaken claims** (someone claims a found child). → handover
  verification workflow required before any reunification.
- **Same name + same village, different people.** → require ≥2 strong signals.
- **Person drifts after being found** (logged at A, now near B). → time-decay on
  geo; re-match on movement.
- **Status awareness:** skip/flag records already `Reunited` or
  `Transferred to hospital`; surface deceased cases carefully.
- **Scale:** matching is currently O(reports × registry). At 80M-pilgrim scale
  this needs **blocking** (gender × age × zone) + an ANN index (FAISS/pgvector)
  for face embeddings. The blocking keys already exist in the data.
- **Offline/sync:** this build is a single in-memory node. Production needs the
  SQLite-node + Postgres-centre + append-only sync log from PLAN.md.
- **Minors / consent / biometric retention** — see Privacy + Open Questions.

---

## Open questions for the team (please decide)

1. **Does the official/government registry have face photos** (Aadhaar/ID)? If
   yes, face matching can run live↔registry too; today the CSV is text-only so
   face is live↔live and the registry is matched on text/demographics/geo.
2. **Will intake capture GPS** (kiosk location / found location)? It massively
   improves geo matching; right now it's optional and we fall back to text.
3. **Which languages to prioritise** for voice, and is **on-device translation**
   required (network dies at the ghats) or is a cloud translate acceptable?
4. **Handover verification:** who authorises releasing a found person to a
   claimant, and what proof? This gates the whole reunification step.
5. **Photo retention:** store embeddings only (privacy) or keep raw photos for
   operator review? For how long after the mela?
6. **Center hardware:** can nodes run Whisper-small + dlib on CPU, or do we need
   tiny models / a shared GPU box?
7. **Use resolution status?** Should we exclude already-`Reunited` records from
   candidate pools by default?
8. **Expected reports/center/day** → tells us whether to add blocking + ANN now.
9. **For the unconscious**, do we also capture a fallback biometric (fingerprint)
   when no photo is usable?
10. **PA / GGTalk integration** — the registry remarks reference these; should a
    confirmed match auto-draft a PA announcement?

---

## Privacy by design

- Biometrics (face embedding, photo path) are **never** returned in API
  responses — `Report.public_dict()` strips them.
- Matches are suggestions; a human confirms every merge/handover.
- Recommended production policy: store embeddings not raw photos where possible,
  consent logged at intake, purpose-bound TTL that purges personal data after
  the mela, full audit log of every search/view/merge.
