"""Simulated camera network.

Turns gallery faces into camera *observations* so a retrieval hit maps to a
location + time (the whole point: "this missing person was seen at camera X").
GPS is grounded on the real CCTV_Locations.csv when available, else synthesised
around the Nashik/Trimbak grid.

Each observation: camera_id, timestamp, lat, lng, crowd_density, confidence,
face_bbox, embedding_id.  No real surveillance data is used.
"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np


@dataclass
class Observation:
    embedding_id: int
    camera_id: str
    timestamp: str
    lat: float
    lng: float
    crowd_density: float      # 0..1
    confidence: float         # detector/recognition confidence 0..1
    face_bbox: list           # [x1, y1, x2, y2]


def load_cameras(cfg: dict, base_dir: str) -> list[dict]:
    n = int(cfg.get("num_cameras", 32))
    csv_path = cfg.get("cctv_csv", "")
    if csv_path and not os.path.isabs(csv_path):
        csv_path = os.path.normpath(os.path.join(base_dir, csv_path))
    cams: list[dict] = []
    if cfg.get("use_cctv_csv") and csv_path and os.path.isfile(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    cams.append({"camera_id": r["camera_id"],
                                 "lat": float(r["latitude"]),
                                 "lng": float(r["longitude"])})
                except (KeyError, ValueError):
                    continue
    if not cams:  # synthesise around Nashik if no CSV
        rng = np.random.default_rng(int(cfg.get("seed", 42)))
        for i in range(n):
            cams.append({"camera_id": f"SIM-C{i+1:03d}",
                         "lat": 19.99 + float(rng.uniform(-0.05, 0.05)),
                         "lng": 73.78 + float(rng.uniform(-0.07, 0.07))})
    # spread the gallery across at most n cameras
    return cams[:n] if n and len(cams) > n else cams


def simulate_observations(cfg: dict, base_dir: str, embedding_ids: list[int],
                          bboxes: Optional[list] = None,
                          scores: Optional[list] = None) -> list[dict]:
    rng = np.random.default_rng(int(cfg.get("seed", 42)))
    cams = load_cameras(cfg, base_dir)
    start = datetime.fromisoformat(cfg.get("start_time", "2027-07-14T06:00:00"))
    window = int(cfg.get("time_window_minutes", 720))
    obs = []
    for k, eid in enumerate(embedding_ids):
        cam = cams[int(rng.integers(0, len(cams)))]
        ts = start + timedelta(minutes=float(rng.uniform(0, window)))
        bbox = bboxes[k] if bboxes and k < len(bboxes) and bboxes[k] else \
            [0, 0, 112, 112]
        conf = float(scores[k]) if scores and k < len(scores) and scores[k] else \
            float(rng.uniform(0.6, 0.99))
        obs.append(asdict(Observation(
            embedding_id=int(eid),
            camera_id=cam["camera_id"],
            timestamp=ts.isoformat(timespec="seconds"),
            lat=cam["lat"], lng=cam["lng"],
            crowd_density=round(float(rng.uniform(0.1, 1.0)), 3),
            confidence=round(conf, 3),
            face_bbox=[int(v) for v in bbox],
        )))
    return obs


def observations_by_embedding(obs: list[dict]) -> dict[int, dict]:
    return {o["embedding_id"]: o for o in obs}
