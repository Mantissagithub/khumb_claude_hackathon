"""Face-search verdict engine (Feature 1, PLAN.md).

Wraps the real `face_retrieval` pipeline and turns a raw cosine score into an
operator-facing, EXPLAINABLE verdict: is this the same person, how confident,
and *why* — across supporting still images OR CCTV video footage.

Kept framework-free (no FastAPI here) so the brains are unit-testable; the
router is a thin HTTP layer on top.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

# make the top-level `face_retrieval` package importable regardless of cwd
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from face_retrieval.config import get_logger, load_config, set_seed       # noqa: E402
from face_retrieval.pipeline import SearchPipeline                        # noqa: E402

# Verdict bands for facenet/ArcFace cosine on L2-normalised embeddings.
STRONG, LIKELY, WEAK = 0.62, 0.45, 0.32
POLICE_CSV = os.path.join(_REPO, "data", "data", "Police_Stations.csv")
GALLERY_DIR = os.environ.get("FACE_GALLERY_DIR",
                             os.path.join(_REPO, "backend", "_testdata", "faces"))


def _confidence_pct(score: float) -> float:
    return round(max(0.0, min(1.0, (score - 0.2) / 0.6)) * 100, 1)


def _band(score: float) -> tuple[str, str]:
    if score >= STRONG:
        return "STRONG", "Match — very likely the same person"
    if score >= LIKELY:
        return "LIKELY", "Likely the same person"
    if score >= WEAK:
        return "POSSIBLE", "Possible — needs human review"
    return "NO_MATCH", "No match found"


def _haversine_km(a, b) -> float:
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp = math.radians(b[0] - a[0]); dl = math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def _build_verdict(best: float, second: float | None, corroboration: int,
                   face_px: int | None, where: str | None = None) -> dict:
    band, label = _band(best)
    reasons = [f"Face similarity {best:.2f} (cosine) — {band.lower()} similarity."]
    if corroboration >= 2:
        reasons.append(f"Corroborated across {corroboration} supporting image(s)/frame(s).")
    if second is not None and (best - second) >= 0.12:
        reasons.append(f"Clear margin (+{best - second:.2f}) over the next-closest face.")
    if face_px is not None:
        reasons.append(f"Good-quality face crop ({face_px}px) — reliable."
                       if face_px >= 80 else
                       f"Small face crop ({face_px}px) — lower reliability; treat as a lead.")
    if where:
        reasons.append(where)
    reasons.append("Decision support only — a trained operator must visually "
                   "confirm before any reunification.")
    return {"verdict": label, "band": band, "is_match": best >= LIKELY,
            "confidence_pct": _confidence_pct(best), "score": round(best, 4),
            "reasons": reasons}


class FaceSearchService:
    """Process-wide singleton — loads the face model once."""
    _instance: "FaceSearchService | None" = None

    def __init__(self):
        self.cfg = load_config()
        set_seed(int(self.cfg.project.seed))
        self.log = get_logger("face_search", self.cfg.logging.level)
        self.pipe = SearchPipeline(self.cfg, self.log)   # owns the FaceEmbedder
        self.thr = float(self.cfg.vector_db.get("match_threshold", 0.45))
        self.police = self._load_police()
        self._gallery_ready = False
        self.audit_path = os.path.join(self.cfg.paths.output_dir, "audit_log.jsonl")

    @classmethod
    def get(cls) -> "FaceSearchService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -- responsible-data audit (no biometrics / no raw images stored) ------
    def audit(self, action: str, consent: bool, extra: dict | None = None) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "action": action, "consent": bool(consent)}
        if extra:
            rec.update(extra)
        try:
            with open(self.audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass

    def _annotate(self, scene_path: str, bbox, label: str, others=None) -> str | None:
        """Draw the located face on the image — what the UI shows the operator."""
        from face_retrieval.modules import visualization as viz
        out = os.path.join(self.cfg.paths.output_dir,
                           "annotated_" + os.path.basename(scene_path) + ".png")
        try:
            return viz.highlight_in_scene(scene_path, bbox, out, others or [], label=label)
        except Exception:
            return None

    def _load_police(self) -> list[dict]:
        out = []
        if os.path.isfile(POLICE_CSV):
            with open(POLICE_CSV, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    try:
                        out.append({"name": r["station_name"].strip(),
                                    "lat": float(r["latitude"]),
                                    "lng": float(r["longitude"])})
                    except (KeyError, ValueError):
                        continue
        return out

    def _route_to_police(self, lat, lng) -> dict | None:
        if lat is None or lng is None or not self.police:
            return None
        best = min(self.police, key=lambda p: _haversine_km((lat, lng), (p["lat"], p["lng"])))
        d = _haversine_km((lat, lng), (best["lat"], best["lng"]))
        return {"to": best["name"], "lat": best["lat"], "lng": best["lng"],
                "steps": [f"Escort to {best['name']} (~{d:.1f} km from the sighting).",
                          "Hand over with the case ID; log the reunification."]}

    # -- 1) verify against supporting still images --------------------------
    def verify(self, query_path: str, support_paths: list[str],
               consent: bool = False) -> dict:
        q = self.pipe.embedder.embed_image(query_path)
        if q is None:
            self.audit("verify", consent, {"result": "no_query_face"})
            return {"ok": False, "verdict": "Cannot assess",
                    "reasons": ["No face detected in the reference photo. "
                                "Use a clearer, front-facing photo."]}
        per_image, scored = [], []
        for sp in support_paths:
            faces = self.pipe.embedder.embed_image_faces(sp)
            name = os.path.basename(sp)
            if not faces:
                per_image.append({"image": name, "faces_found": 0, "best_score": None})
                continue
            sims = [float(np.dot(q, f[0])) for f in faces]
            bi = int(np.argmax(sims))
            bbox = [int(v) for v in faces[bi][1]]
            per_image.append({"image": name, "faces_found": len(faces),
                              "best_score": round(sims[bi], 4), "bbox": bbox,
                              "is_match": sims[bi] >= self.thr})
            scored.append((sims[bi], bbox, name))
        if not scored:
            self.audit("verify", consent, {"result": "no_support_faces"})
            return {"ok": True, "verdict": "No match found",
                    "is_match": False, "confidence_pct": 0.0, "reasons":
                    ["No faces detected in the supporting images."],
                    "per_image": per_image}
        scored.sort(reverse=True)
        best_score, best_bbox, best_img = scored[0]
        second = scored[1][0] if len(scored) > 1 else None
        corro = sum(1 for s, _, _ in scored if s >= self.thr)
        face_px = min(best_bbox[2] - best_bbox[0], best_bbox[3] - best_bbox[1])
        verdict = _build_verdict(best_score, second, corro, face_px,
                                 where=f"Best match in: {best_img}.")
        best_path = next((sp for sp in support_paths
                          if os.path.basename(sp) == best_img), None)
        annotated = self._annotate(best_path, best_bbox,
                                   f"{verdict['confidence_pct']:.0f}%") if best_path else None
        verdict.update({"ok": True, "best_image": best_img, "best_bbox": best_bbox,
                        "annotated_path": annotated, "per_image": per_image})
        self.audit("verify", consent, {"result": verdict["band"],
                                       "n_support": len(support_paths)})
        return verdict

    # -- 2) search a CCTV video clip ----------------------------------------
    def search_footage(self, query_path: str, video_path: str,
                       max_frames: int = 60, every_sec: float = 1.5,
                       consent: bool = False) -> dict:
        n = self.pipe.build_gallery_from_video(video_path, max_frames=max_frames,
                                               every_sec=every_sec)
        res = self.pipe.find_in_crowd(query_path, top_k=10)
        if not res:
            self.audit("search_footage", consent, {"result": "no_query_face"})
            return {"ok": False, "verdict": "Cannot assess",
                    "reasons": ["No face detected in the reference photo."]}
        top = res["matches"][0]
        second = res["matches"][1]["score"] if len(res["matches"]) > 1 else None
        corro = sum(1 for m in res["matches"] if m["confident"])
        face_px = min(int(top["bbox"][2] - top["bbox"][0]),
                      int(top["bbox"][3] - top["bbox"][1]))
        timeline = sorted({m["time_sec"] for m in res["matches"] if m["confident"]})
        verdict = _build_verdict(
            top["score"], second, corro, face_px,
            where=f"First clear sighting at {top['timestamp']} in the footage.")
        others = [m["bbox"] for m in self.pipe.crowd_meta
                  if m["scene_path"] == top["scene_path"]]
        annotated = self._annotate(top["scene_path"], top["bbox"],
                                   f"{verdict['confidence_pct']:.0f}% @ {top['timestamp']}",
                                   others)
        verdict.update({"ok": True, "frames_sampled": n,
                        "best_frame": top["scene_path"], "best_bbox": top["bbox"],
                        "annotated_path": annotated,
                        "appearances_sec": [round(t, 1) for t in timeline],
                        "matches": res["matches"][:6]})
        self.audit("search_footage", consent,
                   {"result": verdict["band"], "appearances": len(timeline)})
        return verdict

    # -- 3) frozen contract: POST /api/face/search vs a camera gallery ------
    def _ensure_gallery(self):
        if self._gallery_ready:
            return
        from face_retrieval.modules.dataset_loader import load_sample_folder
        scenes = load_sample_folder(GALLERY_DIR)
        if not scenes:
            raise RuntimeError(f"empty face gallery at {GALLERY_DIR}")
        self.pipe.build_crowd_gallery(scenes)   # per-face, GPS-tagged cameras
        self._gallery_ready = True

    def search_gallery(self, query_path: str, top_k: int = 5,
                       consent: bool = False) -> dict:
        self._ensure_gallery()
        res = self.pipe.find_in_crowd(query_path, top_k=top_k)
        if not res:
            return {"matches": [], "route": None,
                    "verdict": "Cannot assess", "reasons": ["No face in query."]}
        matches = []
        for m in res["matches"]:
            matches.append({
                "case_id": os.path.splitext(os.path.basename(m["scene_path"]))[0],
                "score": m["score"], "camera_id": m["camera_id"],
                "lat": m.get("lat"), "lng": m.get("lng"),
                "matched_name": None, "timestamp": m.get("timestamp"),
                "confident": m["confident"]})
        top = res["matches"][0]
        route = self._route_to_police(top.get("lat"), top.get("lng")) \
            if res["confident_match"] else None
        second = res["matches"][1]["score"] if len(res["matches"]) > 1 else None
        verdict = _build_verdict(top["score"], second,
                                 sum(1 for m in res["matches"] if m["confident"]),
                                 None,
                                 where=(f"Seen on camera {top['camera_id']}."
                                        if res["confident_match"] else None))
        self.audit("face_search", consent, {"result": verdict["band"]})
        return {**verdict, "matches": matches, "route": route}
