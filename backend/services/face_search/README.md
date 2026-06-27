# Feature 1 — Face Search with an Explainable Verdict

The winning angle: instead of dumping a list of scores, the operator gets a
plain-language **"Is this them?" verdict — yes / likely / no — with a confidence
%, the *reasons why*, and a "where/when" that routes to action**. A family
member (often non-literate, phoneless) can have it read aloud; a machine never
makes the final call.

Wraps the real [`face_retrieval`](../../../face_retrieval/) engine
(detect → ArcFace/FaceNet embed → FAISS) and adds the verdict, routing, consent
and audit layers.

## Endpoints (`/api/face`)

| Method | Path | Input | Output |
|---|---|---|---|
| GET | `/health` | — | model/backends + threshold |
| POST | `/search` | `image` (+`aadhaar`) multipart | gallery matches + nearest-police `route` + verdict *(frozen PLAN.md contract, extended)* |
| POST | `/verify` | `image` + `support[]` + `consent_given` | verdict: is the person in the supporting images? |
| POST | `/search-footage` | `image` + `video` + `consent_given` | verdict + appearance timeline + annotated frame |

### Verdict shape (all endpoints)
```jsonc
{
  "verdict": "Match — very likely the same person",
  "band": "STRONG",            // STRONG | LIKELY | POSSIBLE | NO_MATCH
  "is_match": true,
  "confidence_pct": 96.8,
  "score": 0.78,               // cosine
  "reasons": [
    "Face similarity 0.78 (cosine) — strong similarity.",
    "Clear margin (+0.34) over the next-closest face.",
    "Good-quality face crop (133px) — reliable.",
    "Decision support only — a trained operator must visually confirm ..."
  ],
  "per_image": [ { "image": "...", "best_score": 0.78, "bbox": [..], "is_match": true } ],
  "annotated_frame": "data:image/png;base64,...",   // the face boxed, for the UI
  "appearances_sec": [7.4, 8.9, 42.9],              // footage only
  "route": { "to": "Satpur Police station", "lat": .., "lng": .., "steps": [..] }  // search only
}
```

### Example
```bash
curl -F image=@missing.jpg -F support=@cam1.jpg -F support=@cam2.jpg \
     -F consent_given=true  http://localhost:8000/api/face/verify

curl -F image=@missing.jpg -F video=@cctv.mp4 -F consent_given=true \
     http://localhost:8000/api/face/search-footage
```

## Why this wins on every judging criterion

| Criterion | How this feature scores |
|---|---|
| **Deployability at scale** | Local models + FAISS; runs CPU-only and offline; `/search` reuses a prebuilt camera gallery; backends auto-fallback (insightface→facenet, faiss→numpy). |
| **Real-world fit** | Directly closes the cross-center gap: a clean report photo → located on a camera/clip → **auto-routed to the nearest police station** to act. |
| **UX (phoneless / non-literate)** | Output is a single spoken-language verdict + confidence the operator reads aloud; an annotated image *shows* the match; no typing or literacy required by the family. |
| **System design** | Works on **incomplete data** (face only — no name/phone needed); a **confidence threshold** gates every result, so a wrong identity is never asserted (returns "needs human review"); handles crowds/video (many faces per frame). |
| **Responsible data handling** | `consent_given` is **required** for image/video ingestion; every call is **audit-logged**; biometrics and raw uploads are **never returned** and uploads are **deleted after processing**; the verdict always states a human must confirm. |

## Run

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt -r ../face_retrieval/requirements.txt
uvicorn main:app --reload --port 8000      # docs at /docs
```

> Note: this machine's *global* FastAPI install is corrupted — always run inside
> a fresh venv. The verdict engine (`logic.py`) is framework-free and verified
> independently of the HTTP layer.
