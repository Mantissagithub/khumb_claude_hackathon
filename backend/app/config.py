"""Central configuration: data paths, thresholds and fusion weights.

Everything tunable lives here so the matching behaviour can be adjusted
without touching the algorithms. Weights are deliberately explainable:
the final score is a transparent weighted sum of per-signal similarities.
"""
from __future__ import annotations

from pathlib import Path

# --- Paths -----------------------------------------------------------------
# backend/app/config.py -> repo root is two parents up from this file's dir.
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "data"

MISSING_CSV = DATA_DIR / "Synthetic_Missing_Persons_2500.csv"
CCTV_CSV = DATA_DIR / "CCTV_Locations.csv"
ZONES_CSV = DATA_DIR / "Zone_Boundaries.csv"
POLICE_CSV = DATA_DIR / "Police_Stations.csv"
CHOKEPOINTS_CSV = DATA_DIR / "Chokepoints_Parking.csv"

# Where uploaded photos / audio are stored at runtime.
UPLOAD_DIR = REPO_ROOT / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Matching thresholds ---------------------------------------------------
# A pair scoring >= AUTO_REVIEW is surfaced to an operator's review queue.
# Nothing is ever merged automatically (human-in-the-loop, see README).
AUTO_REVIEW = 0.72
# Candidates between SHOW and AUTO_REVIEW appear as ranked suggestions.
SHOW = 0.40

# Face distance below this (lower = more similar) counts as a strong face hit.
# 0.6 is the widely-used face_recognition/dlib default; we tighten slightly.
FACE_MATCH_DISTANCE = 0.55

# Geography: a CCTV camera within this many metres of a point is "nearby".
CCTV_NEARBY_METERS = 300.0

# --- Fusion weights --------------------------------------------------------
# Base weights per signal. The engine re-normalises over whichever signals
# are actually available for a given pair (dynamic weighting), so a report
# with no name/photo still matches well on description + geo + demographics.
WEIGHTS = {
    "face": 0.34,
    "cloth": 0.14,
    "name": 0.16,
    "mobile": 0.12,
    "demographics": 0.10,  # gender + age_band + state/district + language
    "description": 0.08,
    "geo": 0.06,
}

# Age bands as they appear in the dataset, in order (used for adjacency).
AGE_BANDS = ["0-12", "13-17", "18-40", "41-60", "61-70", "71-80", "80+"]
