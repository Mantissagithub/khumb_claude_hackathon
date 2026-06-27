"""Cloth / appearance matching from a photo.

Faces are often unclear at Kumbh (crowds, distance, elderly), so clothing
colour is a valuable secondary signal. We extract the dominant clothing
colours from the lower ~60% of the person crop (torso/legs, away from the
face) and map them to the SAME canonical colour vocabulary used by the text
matcher (text.COLOR_SYNONYMS). That lets a photo's colours match a typed or
*spoken* description like "saffron kurta".

Needs only Pillow + numpy. If absent, `available = False` and the system
falls back to text-derived appearance similarity.
"""
from __future__ import annotations

from typing import Optional

try:
    import numpy as np
    from PIL import Image
    available = True
except Exception:  # pragma: no cover
    available = False

# Canonical colour reference points in RGB (match text.COLOR_SYNONYMS keys).
_COLOR_REF = {
    "white": (245, 245, 245),
    "black": (25, 25, 25),
    "red": (200, 30, 30),
    "green": (40, 140, 60),
    "blue": (40, 70, 180),
    "yellow": (230, 210, 60),
    "saffron": (240, 140, 30),
    "orange": (240, 110, 30),
    "brown": (120, 80, 50),
    "pink": (230, 130, 170),
    "grey": (128, 128, 128),
    "purple": (120, 60, 150),
    "cream": (235, 225, 200),
}


def _nearest_color(rgb) -> str:
    best, best_d = "grey", float("inf")
    for name, ref in _COLOR_REF.items():
        d = sum((int(a) - b) ** 2 for a, b in zip(rgb, ref))
        if d < best_d:
            best, best_d = name, d
    return best


def signature(image_path: str, top_k: int = 3) -> Optional[dict]:
    """Return {canonical_color: fraction} for the dominant clothing colours.

    Returns None if image libs are unavailable or the image can't be read.
    """
    if not available:
        return None
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    w, h = img.size
    # Focus on torso/legs: drop the top 35% (head) to avoid skin/face pixels.
    crop = img.crop((0, int(h * 0.35), w, h))
    crop.thumbnail((64, 64))
    arr = np.asarray(crop).reshape(-1, 3)

    counts: dict[str, int] = {}
    for px in arr:
        # Skip near-skin / very low-saturation handled implicitly by nearest-ref.
        name = _nearest_color(px)
        counts[name] = counts.get(name, 0) + 1

    total = sum(counts.values()) or 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return {name: round(c / total, 3) for name, c in ranked}


def score_sig_sig(a: Optional[dict], b: Optional[dict]) -> Optional[float]:
    """Histogram intersection between two colour signatures (0..1)."""
    if not a or not b:
        return None
    keys = set(a) | set(b)
    return sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)


def score_sig_text(sig: Optional[dict], text_colors: set) -> Optional[float]:
    """How well a photo's colours match colours mentioned in text (0..1)."""
    if not sig or not text_colors:
        return None
    present = sum(sig.get(c, 0.0) for c in text_colors)
    # Reward overlap; presence of any mentioned colour in the top colours.
    hit = 1.0 if any(c in sig for c in text_colors) else 0.0
    return max(present, 0.6 * hit)
