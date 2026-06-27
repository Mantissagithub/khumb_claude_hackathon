"""Face matching — free, offline, pre-trained models only (per the brief).

Priority of backends (all free / local, no API keys):
  1. `face_recognition` (dlib ResNet, 128-d) — simplest, robust.
  2. `deepface` (e.g. Facenet/ArcFace) — fallback if dlib won't build.
If neither is installed the module reports `available = False`; the rest of
the system keeps working on text + cloth + geo signals.

We store only the numeric embedding, never the raw photo where avoidable
(privacy by design — see README).
"""
from __future__ import annotations

import math
from typing import Optional

_BACKEND = None
_face_recognition = None
_deepface = None

try:
    import face_recognition as _face_recognition  # type: ignore
    _BACKEND = "face_recognition"
except Exception:
    try:
        from deepface import DeepFace as _deepface  # type: ignore
        _BACKEND = "deepface"
    except Exception:
        _BACKEND = None

available = _BACKEND is not None
backend_name = _BACKEND or "none"


def embed(image_path: str) -> Optional[list[float]]:
    """Return a face embedding for the largest/first face, or None if no face."""
    if _BACKEND == "face_recognition":
        img = _face_recognition.load_image_file(image_path)
        encs = _face_recognition.face_encodings(img)
        return encs[0].tolist() if encs else None
    if _BACKEND == "deepface":
        try:
            reps = _deepface.represent(img_path=image_path,
                                       model_name="Facenet",
                                       enforce_detection=True)
            return reps[0]["embedding"] if reps else None
        except Exception:
            return None
    return None


def _euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return 1.0 - dot / (na * nb)


def distance(a: list[float], b: list[float]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    # dlib encodings compare by euclidean; deepface embeddings by cosine.
    return _euclidean(a, b) if _BACKEND == "face_recognition" else _cosine_distance(a, b)


def score(a: Optional[list[float]], b: Optional[list[float]]) -> Optional[float]:
    """Map face distance to a 0..1 similarity. None if either embedding absent."""
    d = distance(a, b) if a and b else None
    if d is None:
        return None
    # Linear map: distance 0 -> 1.0, distance ~0.9 -> 0.0 (clamped).
    return max(0.0, min(1.0, 1.0 - d / 0.9))
