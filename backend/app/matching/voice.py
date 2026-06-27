"""Cross-language voice matching.

A phoneless / non-literate pilgrim (or an operator) speaks in any language
(Marathi, Hindi, Telugu, Maithili, ...). We:
  1. transcribe + auto-translate to English with Whisper (free, offline,
     pre-trained — task='translate' does speech->English in one pass), then
  2. parse the English text into a structured query (appearance, gender,
     age, possible last-seen location) reusing the same vocabulary as the
     text matcher, so a spoken "lal saree, budhi aurat" lands on the same
     tags as a typed "old woman in red saree".

Backends (free/local): faster-whisper preferred, openai-whisper fallback.
If neither is present, `available = False`.
"""
from __future__ import annotations

import re
from typing import Optional

from . import text as T

_BACKEND = None
_fw_model = None
_whisper = None

try:
    from faster_whisper import WhisperModel as _FWModel  # type: ignore
    _BACKEND = "faster_whisper"
except Exception:
    try:
        import whisper as _whisper  # type: ignore
        _BACKEND = "whisper"
    except Exception:
        _BACKEND = None

available = _BACKEND is not None
backend_name = _BACKEND or "none"


def _get_fw():
    global _fw_model
    if _fw_model is None:
        # "small" is a good CPU/accuracy trade-off for an on-site laptop.
        _fw_model = _FWModel("small", device="cpu", compute_type="int8")
    return _fw_model


def transcribe(audio_path: str) -> dict:
    """Return {language, text (native), translated (English)}."""
    if _BACKEND == "faster_whisper":
        model = _get_fw()
        # native transcription (keeps original language)
        seg_n, info = model.transcribe(audio_path)
        native = " ".join(s.text for s in seg_n).strip()
        # english translation
        seg_e, _ = model.transcribe(audio_path, task="translate")
        english = " ".join(s.text for s in seg_e).strip()
        return {"language": info.language, "text": native, "translated": english}
    if _BACKEND == "whisper":
        model = _whisper.load_model("small")
        native = model.transcribe(audio_path)
        english = model.transcribe(audio_path, task="translate")
        return {
            "language": native.get("language", "unknown"),
            "text": native.get("text", "").strip(),
            "translated": english.get("text", "").strip(),
        }
    raise RuntimeError("No speech backend installed (faster-whisper or whisper).")


_GENDER_WORDS = {
    "Male": ["man", "male", "boy", "old man", "gentleman", "aadmi", "admi",
             "purush", "ladka", "baba", "kaka", "ajoba"],
    "Female": ["woman", "female", "girl", "lady", "old woman", "aurat",
               "mahila", "stri", "bai", "ladki", "maushi", "aaji", "amma"],
}


def _detect_gender(t: str) -> Optional[str]:
    t = T.normalize(t)
    for gender, forms in _GENDER_WORDS.items():
        if any(re.search(r"\b" + re.escape(f) + r"\b", t) for f in forms):
            return gender
    return None


def _detect_age_band(t: str) -> Optional[str]:
    t = T.normalize(t)
    m = re.search(r"\b(\d{1,3})\s*(years|year|saal|sal|varsh|varsha|yrs)?\b", t)
    if m:
        age = int(m.group(1))
        for lo, hi, band in [(0, 12, "0-12"), (13, 17, "13-17"), (18, 40, "18-40"),
                             (41, 60, "41-60"), (61, 70, "61-70"), (71, 80, "71-80")]:
            if lo <= age <= hi:
                return band
        if age > 80:
            return "80+"
    # qualitative cues
    if re.search(r"\b(old|elderly|budha|budhi|vrudh|mhatara|mhatari)\b", t):
        return "61-70"
    if re.search(r"\b(child|kid|baby|bachcha|lahan|mulga|muli)\b", t):
        return "0-12"
    return None


def parse_query(translated_text: str) -> dict:
    """Turn translated speech into a structured, matchable query dict."""
    appearance = T.extract_appearance(translated_text)
    return {
        "source": "voice",
        "type": "missing",  # a searching family describes a missing person
        "name": "",         # spoken names are unreliable; left for operator to confirm
        "gender": _detect_gender(translated_text) or "",
        "age_band": _detect_age_band(translated_text) or "",
        "physical_description": translated_text,
        "last_seen_location": translated_text,  # engine resolves via gazetteer
        "appearance": {k: sorted(v) for k, v in appearance.items()},
        "raw_text": translated_text,
    }
