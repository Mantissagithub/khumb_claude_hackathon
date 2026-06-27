"""Text, demographic and cloth-from-text matching.

This is the always-available backbone: it needs no ML models and no network,
so the registry is searchable and de-duplicating from the moment it boots.
Face / cloth-image / voice signals layer on top when their deps are present.

`rapidfuzz` is used when installed (fast, good Indic transliteration tolerance);
otherwise we fall back to the stdlib difflib so nothing hard-breaks.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from .. import config

try:  # optional but recommended
    from rapidfuzz import fuzz as _rf

    def _ratio(a: str, b: str) -> float:
        return _rf.token_sort_ratio(a, b) / 100.0
except Exception:  # pragma: no cover - fallback path
    from difflib import SequenceMatcher

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


# --- Normalisation ---------------------------------------------------------
def normalize(text: Optional[str]) -> str:
    t = unicodedata.normalize("NFKC", (text or "")).lower().strip()
    return re.sub(r"\s+", " ", t)


def normalize_mobile(m: Optional[str]) -> str:
    """Keep last 10 digits — strips +91, spaces, separators."""
    digits = re.sub(r"\D", "", m or "")
    return digits[-10:] if len(digits) >= 10 else digits


# --- Cloth / appearance vocabulary (multilingual, transliterated) ----------
# Maps many surface forms to a canonical tag so an English description and a
# Hindi/Marathi voice transcript land on the same attribute.
COLOR_SYNONYMS = {
    "white": ["white", "safed", "pandhra", "pandhara"],
    "black": ["black", "kala", "kaala"],
    "red": ["red", "lal", "laal", "tambda", "tambada"],
    "green": ["green", "hara", "hari", "hirva", "hirava"],
    "blue": ["blue", "neela", "nila", "nili"],
    "yellow": ["yellow", "peela", "pila", "pivla", "pivala"],
    "saffron": ["saffron", "bhagwa", "bhagva", "kesari", "geru"],
    "orange": ["orange", "narangi"],
    "brown": ["brown", "bhura", "khaki"],
    "pink": ["pink", "gulabi"],
    "grey": ["grey", "gray", "ashen", "raakhadi"],
    "purple": ["purple", "jambhala"],
    "cream": ["cream", "off-white", "beige"],
}
GARMENT_SYNONYMS = {
    "saree": ["saree", "sari", "lugda", "nauvari"],
    "kurta": ["kurta", "kurti", "jhabba"],
    "dhoti": ["dhoti", "dhotar"],
    "shirt": ["shirt", "kameez"],
    "pant": ["pant", "trouser", "pyjama", "pajama"],
    "salwar": ["salwar", "shalwar", "churidar"],
    "lungi": ["lungi"],
    "cap": ["cap", "topi", "gandhi topi"],
    "turban": ["turban", "pagdi", "pheta", "fenta", "safa"],
    "shawl": ["shawl", "shaal", "chaddar", "uparna"],
    "sweater": ["sweater", "jacket", "coat"],
    "blouse": ["blouse", "choli"],
    "frock": ["frock", "dress"],
    "sherwani": ["sherwani", "achkan"],
}
ACCESSORY_SYNONYMS = {
    "rudraksha": ["rudraksha", "rudraksh"],
    "mala": ["mala", "maala", "garland", "beads"],
    "tilak": ["tilak", "tika", "kumkum", "gandh"],
    "glasses": ["glasses", "spectacles", "chashma", "specs"],
    "bangles": ["bangles", "chudiyan", "bangdya"],
    "watch": ["watch", "ghadi"],
    "stick": ["stick", "walking stick", "lathi", "kathi", "cane"],
    "bag": ["bag", "jhola", "thaila", "pishvi"],
    "barefoot": ["barefoot", "no slippers", "anavani"],
    "spectacles": ["spectacles"],
}


def _extract(text: str, table: dict[str, list[str]]) -> set[str]:
    t = normalize(text)
    found = set()
    for canon, forms in table.items():
        for form in forms:
            if re.search(r"\b" + re.escape(form) + r"\b", t):
                found.add(canon)
                break
    return found


def extract_appearance(text: str) -> dict[str, set[str]]:
    """Pull canonical colour / garment / accessory tags from free text."""
    return {
        "colors": _extract(text, COLOR_SYNONYMS),
        "garments": _extract(text, GARMENT_SYNONYMS),
        "accessories": _extract(text, ACCESSORY_SYNONYMS),
    }


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def appearance_similarity_text(desc_a: str, desc_b: str) -> Optional[float]:
    """Cloth/appearance similarity derived purely from text descriptions.

    Returns None when neither side yields any tags (signal absent).
    """
    a, b = extract_appearance(desc_a), extract_appearance(desc_b)
    parts, weights = [], []
    for key, w in (("colors", 0.5), ("garments", 0.35), ("accessories", 0.15)):
        sa, sb = a[key], b[key]
        if sa or sb:
            parts.append(_jaccard(sa, sb) * w)
            weights.append(w)
    if not weights:
        return None
    return sum(parts) / sum(weights)


# --- Field-level scorers ---------------------------------------------------
def name_score(a: str, b: str) -> Optional[float]:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return None  # 15% of records have no name — absent, not a mismatch
    return _ratio(a, b)


def mobile_score(a: str, b: str) -> Optional[float]:
    a, b = normalize_mobile(a), normalize_mobile(b)
    if not a or not b:
        return None
    return 1.0 if a == b else 0.0


def age_band_score(a: str, b: str) -> Optional[float]:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return None
    bands = [x.lower() for x in config.AGE_BANDS]
    if a == b:
        return 1.0
    if a in bands and b in bands and abs(bands.index(a) - bands.index(b)) == 1:
        return 0.5  # adjacent band — partial credit
    return 0.0


def _eq_score(a: str, b: str) -> Optional[float]:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return None
    return 1.0 if a == b else 0.0


def demographics_score(ra: dict, rb: dict) -> Optional[float]:
    """Combine gender + age band + state/district + language into one signal."""
    comps = []
    for fn in (
        lambda: _eq_score(ra.get("gender", ""), rb.get("gender", "")),
        lambda: age_band_score(ra.get("age_band", ""), rb.get("age_band", "")),
        lambda: _eq_score(ra.get("state", ""), rb.get("state", "")),
        lambda: _eq_score(ra.get("district", ""), rb.get("district", "")),
        lambda: _eq_score(ra.get("language", ""), rb.get("language", "")),
    ):
        s = fn()
        if s is not None:
            comps.append(s)
    if not comps:
        return None
    return sum(comps) / len(comps)


def description_score(a: str, b: str) -> Optional[float]:
    """Free-text similarity of physical descriptions (token-overlap based)."""
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return None
    return _ratio(a, b)
